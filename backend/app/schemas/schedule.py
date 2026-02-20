"""Schedule schemas for interval picker and schedule responses."""
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class IntervalType(str, Enum):
    """Supported interval types for schedule picker."""
    minutes = "minutes"
    hours = "hours"
    days = "days"
    weeks = "weeks"


class IntervalSchedule(BaseModel):
    """Interval-based schedule configuration."""
    interval_type: IntervalType
    interval_value: int = Field(gt=0)
    
    @field_validator('interval_value')
    @classmethod
    def validate_interval_value(cls, v, info):
        """Enforce min/max per interval type to prevent unreasonable schedules."""
        interval_type = info.data.get('interval_type')
        if interval_type == IntervalType.minutes and (v < 5 or v > 1440):
            raise ValueError("Minutes: 5-1440 (5min to 1day)")
        if interval_type == IntervalType.hours and (v < 1 or v > 168):
            raise ValueError("Hours: 1-168 (1hr to 1week)")
        if interval_type == IntervalType.days and (v < 1 or v > 365):
            raise ValueError("Days: 1-365")
        if interval_type == IntervalType.weeks and (v < 1 or v > 52):
            raise ValueError("Weeks: 1-52")
        return v


class ScheduleUpdate(BaseModel):
    """Update connector schedule.
    
    Set interval to None to clear the schedule.
    """
    interval: IntervalSchedule | None = None
    execution_timeout: int | None = Field(None, gt=0)  # seconds


class ScheduleResponse(BaseModel):
    """Schedule status response."""
    cron_schedule: str | None
    schedule_enabled: bool
    execution_timeout: int | None
    next_run_time: str | None  # ISO 8601 timestamp
