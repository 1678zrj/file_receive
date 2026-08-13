from pydantic import BaseModel



# 请求模型
class UserLogin(BaseModel):
    username: str
    password: str




# 响应模型
class Token(BaseModel):
    access_token: str
    refresh_token: str


class AccessToken(BaseModel):
    access_token: str