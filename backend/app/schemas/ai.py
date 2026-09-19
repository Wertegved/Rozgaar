from pydantic import BaseModel, Field


class JobDescriptionAutocompleteRequest(BaseModel):
    title: str = Field(default="", max_length=200)
    category: str = Field(default="", max_length=120)
    partial_description: str = Field(min_length=1, max_length=2000)


class JobDescriptionAutocompleteResponse(BaseModel):
    suggestion: str
