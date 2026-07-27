from app.kernel.context import KernelContext
from app.kernel.agent.tools import SideEffect, ToolSpec
from app.kernel.plugins import PluginSpec
from app.plugins.assignment_grading import models  # noqa: F401 - registers ORM models
from app.plugins.assignment_grading.routes import router
from app.plugins.assignment_grading.service import create_assignment, process_assignment_task


def _build_upload_and_grade_tool(context: KernelContext) -> ToolSpec:
    """构建 UploadAndGrade 工具规格"""
    async def upload_and_grade_handler(
        file_path: str,
        subject: str,
        student_id: int,
        title: str | None = None,
        grade: str | None = None,
    ) -> dict:
        """执行批改工作流（直接调用 service 层）"""
        from app.plugins.assignment_grading.workflow import run_grading_workflow
        result = await run_grading_workflow(
            context,
            file_path=file_path,
            subject=subject,
            grade=grade,
            student_id=str(student_id),
        )
        return result.model_dump() if hasattr(result, 'model_dump') else result.dict()

    return ToolSpec(
        name="AssignmentGrading::UploadAndGrade",
        description="上传作业图片或PDF，自动识别题目和手写作答，判分并标注知识点",
        short_intent="批改作业",
        side_effect=SideEffect.WRITE,
        requires_confirmation=False,  # 学生显式上传点击即执行
        handler=upload_and_grade_handler,
        schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "上传文件的存储路径"},
                "subject": {"type": "string", "description": "学科名称"},
                "student_id": {"type": "integer", "description": "学生用户ID"},
                "title": {"type": "string", "description": "作业标题（可选）"},
                "grade": {"type": "string", "description": "年级（可选）"},
            },
            "required": ["file_path", "subject", "student_id"],
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
