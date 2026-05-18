import streamlit as st
import time
from services.config.workout_config import METRICS_FIELDS
from services.persistence.exercise_repository import add_exercise


def sync_metrics_update(context):

    if not context or not hasattr(context, "state") or not context.state.playing:
        return

    processor = getattr(context, "video_processor", None)
    if not processor:
        return

    exercise = st.session_state.get("exercise_type")
    if not exercise:
        return

    processor.set_exercise(exercise)
    latest_metrics = processor.get_latest_metrics()

    if not latest_metrics:
        return


    reps = latest_metrics.get("reps", 0)

    try:
        reps = int(reps)
    except:
        reps = st.session_state.get("reps", 0)

    prev_reps = st.session_state.get("reps", 0)

    # only update if stable or increasing
    if reps >= prev_reps:
        st.session_state.reps = reps

   
    fields = METRICS_FIELDS.get(exercise, {})
    for key, default in fields.items():
        st.session_state[key] = latest_metrics.get(key, default)

    reps_per_set = st.session_state.get("reps_per_set", 0)
    target_sets = st.session_state.get("target_sets", 0)

    sets_completed = 0
    current_set_reps = 0
    workout_completed = False

    if reps_per_set > 0 and target_sets > 0:
        sets_completed = reps // reps_per_set
        current_set_reps = reps % reps_per_set
        workout_completed = sets_completed >= target_sets

    st.session_state.sets_completed = sets_completed
    st.session_state.current_set_reps = current_set_reps
    st.session_state.workout_completed = workout_completed


    last_saved = st.session_state.get("last_saved_sets_completed", 0)

    if sets_completed > last_saved:

        newly_completed = sets_completed - last_saved

        now_ts = time.time()
        started_at = st.session_state.get("set_cycle_started_at", now_ts)

        time_taken = now_ts - started_at
        user_id = st.session_state.get("user_id", 0)

        add_exercise(
            user_id,
            exercise,
            newly_completed * reps_per_set,
            newly_completed,
            time_taken
        )

        st.session_state.last_saved_sets_completed = sets_completed
        st.session_state.set_cycle_started_at = now_ts