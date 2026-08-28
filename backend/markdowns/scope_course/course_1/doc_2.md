```python
@router.post("/login", response_model=Token)
def login(
        response: Response, # 需要用到 Response 对象来设置 Cookie,
        user_in: UserLogin,
        session: Session = Depends(get_session),
        settings: Settings = Depends(get_settings)
):
    # 调用 Service 层进行验证
    # settings: Settings = get_settings()
    user = AuthService.authenticate(session, user_in.username, user_in.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    # 运行到这里说明登录验证通过了，该为用户分别生成两种Token了
    # 1、生成 Access Token（短效）
    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    # 2、生成 Refresh Token（长效）
    refresh_token = create_refresh_token(data={"sub": user.username, "type": "refresh"})
    # 2. 【关键修改】将 Refresh Token 写入 HttpOnly Cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,  # 禁止 JS 读取，防 XSS
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        expires=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        samesite="lax",  # 防 CSRF
        secure=False,  # 开发环境 False (HTTP)，生产环境必须 True (HTTPS)
    )

    # 3、返回 Token
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username,
        "id": user.id,
        "avatar" : user.avatar
    }
```

### 问：为什么这段代码的response.set_cookie能够写入前端的cookie中，它并没有被返回啊

这是一个非常好的问题！很多初学 FastAPI 的开发者都会对这一点感到疑惑。

简单来说：**因为 FastAPI 在底层帮你做了一次“合并”操作。**

下面是具体的原理解析：

### 1. `Response` 对象是 FastAPI 提前准备好的“信封”

当你把 `response: Response` 写在路由函数的参数里时，FastAPI 的依赖注入系统会识别到你需要操作响应体。于是，在执行你的 `login` 函数**之前**，FastAPI 就已经提前创建好了一个空的 `Response` 对象，并把它传给了你的函数。

这就好比 FastAPI 递给了你一个空的“信封”。

### 2. `set_cookie` 是在信封上“盖邮戳”

当你在代码中调用 `response.set_cookie(...)` 时，你实际上是在直接修改 FastAPI 递给你的那个 `Response` 对象的内部状态（具体来说，是往这个 HTTP 响应的 Headers 里面塞入了一段 `Set-Cookie` 的指令）。

你修改的是对象的引用（In-place modification），所以这个“信封”现在已经带上了 Cookie 信息。

### 3. `return` 的数据是“信件内容”

当你的函数最后执行到 `return {...}` 时，你返回的只是普通的 Python 字典（或者 Pydantic 模型）。

此时，FastAPI 的底层处理流程会接管：

1. 它拿到你 return 的字典。
2. 它会将这个字典序列化成 JSON 字符串。
3. 它把这个 JSON 字符串塞进**刚才传给你的那个 `Response` 对象（信封）里**，作为响应体（Body）。
4. 最后，FastAPI 把这个完整的 `Response` 对象发送给前端。

### 总结

因为你修改的 `response` 和 FastAPI 最终发送出去的 `response` 在内存中是**同一个对象**。FastAPI 只是把你的 `return` 值和你在 `response` 上设置的 Cookie 拼接到了一起。

**如果你不用这种“参数注入”的方式，另一种写法是显式返回一个 `Response` 对象：**

Python

```
from fastapi.responses import JSONResponse

@router.post("/login")
def login(user_in: UserLogin, ...):
    # ... 前面的验证逻辑 ...
    
    # 显式构造 Response
    response = JSONResponse(content={
        "access_token": access_token,
        "token_type": "bearer",
        # ...
    })
    
    # 在这个对象上设置 cookie
    response.set_cookie(key="refresh_token", value=refresh_token, ...)
    
    # 直接返回这个对象
    return response
```

这两种写法在功能上是完全等效的。但是，**你代码里的写法（参数注入）是 FastAPI 官方更推荐的**，因为它可以继续保持对 `response_model=Token` 的支持（自动校验返回数据格式并生成 Swagger 文档），而显式返回 `JSONResponse` 会让 `response_model` 失效。

### 问：JSONResponse不是属于response_class吗，为什么会让response_model失效呢

这是一个非常敏锐的问题！我需要澄清一下上一条回复中提到的“失效”具体指的是什么。

准确地说，当你直接返回 `JSONResponse` 时，`response_model` 并没有在接口文档（Swagger UI）**层面失效，而是会在**数据校验和过滤（Runtime Validation & Filtering）层面被跳过。

下面为你拆解 FastAPI 底层对这两者的处理逻辑：

### FastAPI 的响应处理流水线

当你的路由函数执行完毕并返回结果时，FastAPI 的底层逻辑大概是这样的：

1. **检查返回值类型：** FastAPI 首先会看你 return 的东西到底是个什么。
2. **如果是普通数据（如 dict、Pydantic 模型、ORM 对象）：**
   - FastAPI 会把它送进你定义的 `response_model` 中。
   - 帮你做**类型转换**、**数据校验**，并**过滤掉模型里没有的字段**（比如剔除敏感信息）。
   - 校验完毕后，FastAPI 会自动把合法的数据包装进 `response_class`（默认就是 `JSONResponse`）然后返回。
3. **如果返回值已经是 `Response` 的实例（如 `JSONResponse`）：**
   - FastAPI 会认为：“既然开发者已经手动构造了底层的 Response 对象，那说明他知道自己在干什么，我就不插手了。”
   - 于是，FastAPI **会直接跳过 `response_model` 的校验和序列化步骤**，把你构造的 `JSONResponse` 原封不动地发给前端。

### 为什么说“跳过校验”很危险？

最大的隐患在于**数据泄露（字段过滤失效）**。

假设你有一个包含敏感信息的数据字典，你希望通过 `response_model` 自动过滤掉密码字段：

Python

```
class UserPublic(BaseModel):
    username: str
    email: str
    # 注意：这里没有定义 password 字段

# 错误做法：显式返回 JSONResponse
@router.post("/login", response_model=UserPublic)
def login():
    user_data_from_db = {
        "username": "admin",
        "email": "admin@example.com",
        "password": "super_secret_password" # 敏感数据
    }
    
    # 因为你直接返回了 JSONResponse，FastAPI 不会帮你用 UserPublic 过滤字段！
    # 结果：前端会收到完整的 JSON，包含 password！
    return JSONResponse(content=user_data_from_db)
```

相比之下，如果你按照你原来代码里的做法（直接返回 `dict` 并依赖参数注入的 `Response` 修改 Cookie）：

Python

```
# 正确做法：返回普通字典
@router.post("/login", response_model=UserPublic)
def login(response: Response):
    user_data_from_db = {
        "username": "admin",
        "email": "admin@example.com",
        "password": "super_secret_password"
    }
    
    response.set_cookie(key="token", value="...")
    
    # FastAPI 会拿这个字典去和 UserPublic 对比
    # 发现 UserPublic 里没有 password，就会自动把它剔除！
    # 结果：前端只会收到 username 和 email，同时带有 Cookie。
    return user_data_from_db 
```

### 总结

- **文档层面：** 无论你 return 什么，只要写了 `response_model=Token`，Swagger 文档上依然会显示 `Token` 的结构。
- **运行层面：** 直接返回 `JSONResponse` 会让 FastAPI 放弃对该响应体进行 Pydantic 序列化和字段过滤。

因此，当你既需要**操作底层 HTTP 属性（Header、Cookie）**，又想享受 **Pydantic 的数据自动过滤**时，在参数里注入 `response: Response` 是最完美、最安全的写法。