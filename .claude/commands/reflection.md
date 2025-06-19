You are an expert in prompt engineering, specializing in optimizing AI code assistant instructions for the Claude Code agentic framework. Your task is to analyze and improve the instructions, commands, and configuration of this repository to enhance your performance as a coding agent.

Follow these steps carefully:

### 1. Analysis Phase

First, review the chat history in your context window to understand the recent interactions and goals.

Then, examine the current Claude Code configuration files. Be sure to look at all of them to get a complete picture:
<claude_instructions>
**/CLAUDE.md
/.claude/commands/*
/.claude/settings.json
/.claude/settings.local.json
</claude_instructions>

Analyze the chat history and the configuration files to identify areas that could be improved. Look for:
-   **Inconsistencies:** Contradictions in your responses or instructions.
-   **Misunderstandings:** Instances where you misunderstood user requests.
-   **Clarity & Detail:** Areas where your output could be more detailed, accurate, or clear.
-   **Command Enhancement:** Opportunities for new commands, or improvements to an existing command's name, function, or response format.
-   **Task Handling:** Ways to enhance your ability to handle specific or complex coding tasks relevant to this repository.
-   **Configuration Drift:** Permissions or capabilities (MCPs) that have been approved or used in practice but are not yet reflected in the `.claude/settings.json` file.

### 2. Interaction Phase

Present your findings and improvement ideas to the human one by one. For each suggestion, you must:
a) Explain the current issue or opportunity you have identified.
b) Propose a specific, concrete change to the files.
c) Describe how this change will improve your performance or capabilities.

**Crucially, you must wait for feedback and approval from the human on each suggestion before proceeding to the next one.** If a suggestion is not approved, refine it based on the feedback or move on to your next idea.

### 3. Implementation Phase

Once a change is approved, you will implement it. For each approved change:
a) Clearly state the file and section you are modifying.
b) Present the new or modified text for that section.
c) Briefly explain how this implemented change addresses the issue identified in your analysis.

### 4. Output Format

Present your final output in the following distinct sections:

<analysis>
[A summary of all the issues and potential improvements you identified in the Analysis Phase.]
</analysis>

<improvements>
[For each approved improvement, provide:
1.  **File & Section:** The file path and section being modified.
2.  **New Text:** The new or modified instruction text.
3.  **Reasoning:** An explanation of how this change addresses the identified issue.]
</improvements>

<final_instructions>
[Present the complete, updated set of instructions for the primary CLAUDE.md file, incorporating all approved changes.]
</final_instructions>

Your ultimate goal is to enhance your performance and consistency while maintaining the core purpose of your role in this repository. Be thorough in your analysis, clear in your explanations, and precise in your implementations.
