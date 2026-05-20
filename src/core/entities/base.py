from pydantic import BaseModel, PositiveInt


class BaseEntity(BaseModel):
    id: PositiveInt | None = None

    model_config = {"from_attributes": True}

    class Creation(BaseModel):
        pass

    class Update(BaseModel):
        pass
