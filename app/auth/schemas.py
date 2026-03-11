from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GitHubCallbackRequest(BaseModel):
    code: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    github_login: str
    email: str | None
    avatar_url: str | None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
