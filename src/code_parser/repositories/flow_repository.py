"""Repository for managing entry point flow documentation."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from code_parser.core import CodeSnippet, EntryPointFlow, FlowStep
from code_parser.database.models import EntryPointFlowModel


class FlowRepository:
    """Data access layer for EntryPointFlow entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_entry_point_id(
        self, entry_point_id: str
    ) -> EntryPointFlowModel | None:
        """Get flow documentation for an entry point."""
        result = await self._session.execute(
            select(EntryPointFlowModel).where(
                EntryPointFlowModel.entry_point_id == entry_point_id
            )
        )
        return result.scalar_one_or_none()

    async def create_or_replace(self, flow: EntryPointFlow) -> None:
        """
        Create or replace flow documentation for an entry point.
        
        If a flow already exists for this entry point, it will be deleted
        and replaced with the new one.
        """
        # Delete existing flow if it exists
        await self.delete_by_entry_point_id(flow.entry_point_id)

        # Convert core model to database model
        steps_json = [
            {
                "step_number": step.step_number,
                "title": step.title,
                "description": step.description,
                "file_path": step.file_path,
                "important_log_lines": step.important_log_lines,
                "important_code_snippets": [
                    {
                        "code": snippet.code,
                        "symbol_name": snippet.symbol_name,
                        "qualified_name": snippet.qualified_name,
                        "file_path": snippet.file_path,
                        "line_range": snippet.line_range,
                    }
                    for snippet in step.important_code_snippets
                ],
            }
            for step in flow.steps
        ]

        model = EntryPointFlowModel(
            id=str(ULID()),
            entry_point_id=flow.entry_point_id,
            repo_id=flow.repo_id,
            flow_name=flow.flow_name,
            technical_summary=flow.technical_summary,
            file_paths=flow.file_paths,
            steps=steps_json,
            max_depth_analyzed=flow.max_depth_analyzed,
            iterations_completed=flow.iterations_completed,
            symbol_ids_analyzed=flow.symbol_ids_analyzed,
        )
        self._session.add(model)
        await self._session.flush()

    async def delete_by_entry_point_id(self, entry_point_id: str) -> None:
        """Delete flow documentation for an entry point."""
        await self._session.execute(
            delete(EntryPointFlowModel).where(
                EntryPointFlowModel.entry_point_id == entry_point_id
            )
        )
        await self._session.flush()

    def model_to_core(self, model: EntryPointFlowModel) -> EntryPointFlow:
        """Convert database model to core model."""
        steps = [
            FlowStep(
                step_number=step_data["step_number"],
                title=step_data["title"],
                description=step_data["description"],
                file_path=step_data.get("file_path", ""),
                important_log_lines=step_data.get("important_log_lines", []),
                important_code_snippets=[
                    CodeSnippet(
                        code=snippet_data["code"],
                        symbol_name=snippet_data["symbol_name"],
                        qualified_name=snippet_data["qualified_name"],
                        file_path=snippet_data["file_path"],
                        line_range=snippet_data["line_range"],
                    )
                    for snippet_data in step_data.get("important_code_snippets", [])
                ],
            )
            for step_data in model.steps
        ]

        return EntryPointFlow(
            entry_point_id=model.entry_point_id,
            repo_id=model.repo_id,
            flow_name=model.flow_name,
            technical_summary=model.technical_summary,
            file_paths=model.file_paths or [],
            steps=steps,
            max_depth_analyzed=model.max_depth_analyzed,
            iterations_completed=model.iterations_completed,
            symbol_ids_analyzed=model.symbol_ids_analyzed or [],
        )
