from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from app.services.rag_search_service import RAGSearchService
from app.core.rag_deps import rag_container
from langgraph.types import interrupt








class RunRAGInput(BaseModel):
    query: str = Field(description="需要检索知识库的问题")


@tool(
    name_or_callable="rag",
    args_schema=RunRAGInput,
    # 这个后续优化的时候再做，现在加上就要求必须返回元组，会报错
    # response_format="content_and_artifact"
)
async def search(query: str, config: RunnableConfig):
    """
    检索知识库中的相关参考文档
    """
    configurable = config.get("configurable") or {}
    scope = configurable.get("scope")
    scope_id = configurable.get("scope_id")
    rag_search_service = RAGSearchService(rag_container)
    result = await rag_search_service.search(query, scope, scope_id)
    return result


class QuestionOption(BaseModel):
    label: str = Field(description="给用户的问题可选项的标签")
    description: str = Field(description="给用户的问题可选项的正文")


class Question(BaseModel):
    id: str = Field(description="问题的唯一简短标识符，英文蛇行命名，用户回复时使用该id标明对应问题答案")
    header: str = Field(description="问题的标题")
    question: str = Field(description="需要向用户询问的核心问题正文")
    options: list[QuestionOption] = Field(
        default_factory=list,
        description="可以选择给用户提供的问题选项，如果需要用户自由文本输入，可留空"
    )


class AskUserQuestionInput(BaseModel):
    questions: list[Question] = Field(
        max_length=3,
        description="需要相关用户批量提问的问题列表，单次提问不超过3个"
    )

"""
该工具的用户回复应该按照此格式：
[
  {
    "id": "upload_mode",
    "selected": [
      "后台任务中心 + 悬浮进度"
    ]
  },
  {
    "id": "multi_select",
    "selected": [
      "支持多文件（推荐）"
    ]
  }
]
注：这是对前端的要求
"""

@tool(name_or_callable="ask_user_question", args_schema=AskUserQuestionInput)
async def ask_user_question(questions: list[Question]):
    """
    当用户意图模糊、缺少执行下游任务的必要业务参数，或者需要用户从多个备选项中做出决策时，
    必须调用此工具暂停并向用户索取必要信息。
    严禁在缺少关键参数时自行捏造或幻觉默认值。
    """
    response = interrupt(
        {
            "action_type": "clarify",
            "questions": [question.model_dump() for question in questions]
        }
    )
    return response




