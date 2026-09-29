from openai import APIError, BadRequestError, AuthenticationError, PermissionDeniedError, UnprocessableEntityError, \
    RateLimitError, InternalServerError, APIStatusError, APIConnectionError, APITimeoutError


class LLMError(Exception):
    is_retryable: bool = False
    def __init__(
            self,
            message: str,
            status_code: int | None = None,
            raw_error: Exception | None = None
    ):
        # Exception底层维护了一个元组，将message传入Exception的初始化函数，则在打印的时候可以打印出来
        # 因为OpenAI的获取大模型响应的异常基类APIError具有message属性
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.raw_error = raw_error


# 定义子异常
class LLMAuthError(LLMError):
    """
    401 API Key错误， 认证失败，不可重试
    对应 openai.AuthenticationError
    """
    is_retryable = False


class LLMRateLimitError(LLMError):
    """
    429限流，可指数退避重试
    对应 openai.RateLimitError
    """
    is_retryable = True


class LLMBadRequestError(LLMError):
    """
    400, 422格式错误，不支持的参数，不可重试
    对应 openai.UnprocessableEntityError
        openai.BadRequestError
    """
    is_retryable = False


class LLMServiceUnavailableError(LLMError):
    """
    500,503,5xx 服务器内部异常，可重试
    对应 openai.InternalServerError
    """
    is_retryable = True

class LLMTimeoutError(LLMError):
    """
    连接超时，可重试
    对应 openai.APIConnectionError
    及其子类 openai.APITimeoutError
    无错误状态码
    """
    is_retryable = True

class LLMUnknownError(LLMError):
    """未知异常，未被定义的异常，默认不重试"""
    is_retryable = False



def normalize_llm_exception(e: Exception) -> LLMError:
    # 导入的OpenAI库的异常的基类
    # 凡是APIError的子类均具有messsage属性
    # 而只有继承APIError的APIStatusError才有status_code属性
    if isinstance(e, APIError):
        # 进行更加细致的区分
        if isinstance(e, AuthenticationError):
            return LLMAuthError(
                message=e.message,
                status_code=e.status_code,
                raw_error=e
            )
        if isinstance(e, RateLimitError):
            return LLMRateLimitError(
                message=e.message,
                status_code=e.status_code,
                raw_error=e
            )
        if isinstance(e, UnprocessableEntityError | BadRequestError):
            return LLMBadRequestError(
                message=e.message,
                status_code=e.status_code,
                raw_error=e
            )
        if isinstance(e, InternalServerError):
            return LLMServiceUnavailableError(
                message=e.message,
                status_code=e.status_code
            )
        if isinstance(e, APIConnectionError | APITimeoutError):
            return LLMTimeoutError(
                message=e.message
            )
    # 当前疑问，当异常不属于APIError及其子类时，该函数应该怎么做
    # 毕竟当前是OpenAI规范下，如果后续还有Anthropic规范呢

    # 状态码兜底
    status_code: int | None = getattr(e, "status_code", None)
    if status_code:
        error_message = str(e)
        if status_code in (401, 403):
            return LLMAuthError(str(e), status_code, raw_error=e)
        if status_code == 429:
            return LLMRateLimitError(error_message, status_code, raw_error=e)
        if status_code in (400, 422):
            return LLMBadRequestError(error_message, status_code, raw_error=e)
        if 500 <= status_code < 600:
            return LLMServiceUnavailableError(error_message, status_code, raw_error=e)
    # 识别不出来的
    return LLMUnknownError(str(e), status_code, raw_error=e)