"""Timeline response models."""

from pydantic import BaseModel


class TimelineItem(BaseModel):
    """A single item on a timeline."""

    id: str
    group: str
    content: str
    start: str
    end: str
    type: str
    class_name: str
    source: str


class TimelineGroup(BaseModel):
    """A group of timeline items."""

    id: str
    content: str
    nested_groups: list[str] | None = None
    show_nested: bool | None = None


class TimelineResponse(BaseModel):
    """Full timeline response with groups and items."""

    groups: list[TimelineGroup]
    items: list[TimelineItem]


class TimelineSummaryResponse(BaseModel):
    """Summary response with a count of timeline items."""

    item_count: int
