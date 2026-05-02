"""Timeline response models."""

from pydantic import BaseModel, ConfigDict, Field


class TimelineItem(BaseModel):
    """A single item on a timeline."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    group: str
    content: str
    start: str
    end: str
    type: str
    class_name: str = Field(alias='className')
    source: str


class TimelineGroup(BaseModel):
    """A group of timeline items."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    content: str
    nested_groups: list[str] | None = Field(default=None, alias='nestedGroups')
    show_nested: bool | None = Field(default=None, alias='showNested')


class TimelineResponse(BaseModel):
    """Full timeline response with groups and items."""

    groups: list[TimelineGroup]
    items: list[TimelineItem]


class TimelineSummaryResponse(BaseModel):
    """Summary response with a count of timeline items."""

    model_config = ConfigDict(populate_by_name=True)

    item_count: int = Field(alias='itemCount')
