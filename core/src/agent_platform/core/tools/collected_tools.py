"""CollectedTools: result type for fetching tools."""

from collections import Counter
from dataclasses import dataclass

from agent_platform.core.tools.tool_definition import ToolDefinition


@dataclass
class CollectedTools:
    """Result from fetching tools."""

    tools: list[ToolDefinition]
    issues: list[str]

    def filter_tools(self, allowed: set[str]) -> None:
        self.tools = [td for td in self.tools if td.name in allowed]

    def merge(self, other: "CollectedTools") -> None:
        if other.issues:
            self.issues.extend(other.issues)

        if other.tools:
            self.tools.extend(other.tools)
            tools, issues = self._deduplicate_tool_names(self.tools)
            self.tools = tools
            if issues:
                self.issues.extend(issues)

    @classmethod
    def _deduplicate_tool_names(
        cls,
        tools: list[ToolDefinition],
    ) -> tuple[list[ToolDefinition], list[str]]:
        """
        Checks for duplicate tool names. The first occurrence of each name
        remains unchanged, while any subsequent occurrences of that same name
        are renamed with a numeric suffix (e.g., "MyTool", "MyTool_2", "MyTool_3", ...).

        Returns:
            A tuple of:
                - The updated list of ToolDefinitions (potentially renamed).
                - A list of messages explaining any renaming that occurred.
        """
        # Count how many times each name appears
        name_counter = Counter(tool.name for tool in tools)
        # We'll track how many times we've assigned a new name
        rename_count = Counter()

        updated_tools: list[ToolDefinition] = []
        issues: list[str] = []

        for tool in tools:
            # If no duplicates for this name, just append as-is
            if name_counter[tool.name] <= 1:
                updated_tools.append(tool)
                continue

            # There's a duplicate for this name. We always allow the first occurrence
            # to keep its name, and rename subsequent occurrences.
            rename_count[tool.name] += 1
            occurrence_index = rename_count[tool.name]

            if occurrence_index == 1:
                # This is the first time we see it in the loop,
                # so keep its original name
                updated_tools.append(tool)
            else:
                # Rename the second or subsequent time, e.g.
                # "toolname_2", "toolname_3", ...
                new_name = f"{tool.name}_{occurrence_index}"
                issues.append(
                    f"Tool with name '{tool.name}' is duplicated. Renaming occurrence "
                    f"#{occurrence_index} to '{new_name}'."
                )
                updated_tools.append(
                    ToolDefinition(
                        name=new_name,
                        description=tool.description,
                        input_schema=tool.input_schema,
                        function=tool.function,
                    )
                )

        return updated_tools, issues
