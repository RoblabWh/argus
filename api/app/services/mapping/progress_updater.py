from sqlalchemy.orm import Session
import app.crud.report as crud
import redis


class ProgressUpdater:
    def __init__(self, report_id: int, redis_client: redis.Redis, session: Session):
        self.report_id = report_id
        self.redis_client = redis_client
        self.session = session
        self.progress = 0.0
        self.map_index = 0
        self.total_maps = 0

    def update_progress(self, status: str, progress: float):
        """
        Update the progress of a report in the database and Redis.
        """
        self.progress = progress

        # Update in database
        crud.update_process(self.session, self.report_id, status, progress)

        # Update in Redis
        self.redis_client.set(f"report:{self.report_id}:progress", progress)

    def update_partial_progress(self, status: str, start:float, end: float, total: float, progress: float):
        """
        Update the progress of a report in the database and Redis with a range.
        """
        diff = end - start

        if diff == 0:
            return 
        new_progress = start + (progress / total) * diff

        # Update in database
        self.update_progress(status, new_progress)

    def update_progress_of_map(self, status: str, progress: float):
        """
        Update the progress of a specific map in the report.
        """
        map_progress = (progress / self.total_maps) + 100 * (self.map_index / self.total_maps)
        self.update_progress(status, map_progress)

    def set_map_index(self, map_index: int, total_maps: int):
        """
        Set the current map index and total maps for progress tracking.
        """
        self.map_index = map_index
        self.total_maps = total_maps