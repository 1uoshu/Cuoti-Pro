from app.kernel.context import KernelContext
from app.kernel.agent.tools import SideEffect, ToolSpec
from app.kernel.plugins import PluginSpec
from app.plugins.assignment_grading import models  # noqa: F401 - registers ORM models
from app.plugins.assignment_grading.routes import router
from app.plugins.assignment_grading.service import create_assignment, process_assignment_task


def _build_upload_and_grade_tool(context: KernelContext) -> ToolSpec:
    """构建 UploadAndGrade 工具规格"""

    async def upload_and_grade_handler(
        assignment_id: int,
        **kwargs,
    ) -> dict:
        """执行批改工作流。

        从数据库读取 assignment 信息，不需要 LLM 传 file_path。
        """
        from app.kernel.database import SessionLocal
        from app.plugins.assignment_grading.models import Assignment
        from app.plugins.assignment_grading.workflow import run_grading_workflow
        from app.kernel.models import User

        with SessionLocal() as db:
            assignment = db.get(Assignment, assignment_id)
            if assignment is None:
                return {"error": f"作业 {assignment_id} 不存在"}
            user = db.get(User, assignment.user_id)
            if user is None:
                return {"error": "用户不存在"}

            result = await run_grading_workflow(
                context,
                assignment.file_path,
                assignment.subject,
                user.grade,
                student_id=str(user.id),
            )
            return result.model_dump() if hasattr(result, 'model_dump') else result.dict()

    return ToolSpec(
        name="AssignmentGrading::UploadAndGrade",
        description="批改已上传的作业。当学生上传作业后，自动调用此工具进行识别、判分、标注知识点。",
        short_intent="批改作业",
        side_effect=SideEffect.WRITE,
        requires_confirmation=False,
        handler=upload_and_grade_handler,
        schema={
            "type": "object",
            "properties": {
                "assignment_id": {"type": "integer", "description": "作业ID（从上传结果中获取）"},
            },
            "required": ["assignment_id"],
        },
    )


def get_plugin(context: KernelContext) -> PluginSpec:
    return PluginSpec(
        name="assignment_grading",
        version="0.1.0",
        description="Uploads homework, runs multimodal grading, and persists structured grading results.",
        routers=(router,),
        dependencies=("mastery_tracking", "wrong_question_book"),
        capabilities=("assignment_upload", "grading_workflow", "question_review"),
        tools=(_build_upload_and_grade_tool(context),),
    )
