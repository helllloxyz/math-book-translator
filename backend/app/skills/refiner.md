# Skill: Refiner
## Description
Updates the textbook blueprint based on user instructions while maintaining structural consistency.

## Context
**Domain**: {domain}
**Current Manifest**:
{current_manifest}

## User Command
"{user_command}"

## Instructions
- You can add, remove, rename, or reorder nodes in the TOC.
- Maintain consistent numbering (e.g., 4.0.0 for Level 1, 4.1 for Level 2).
- Ensure the `vision` for chapters 1-3 remains aligned with the changes if necessary.

## Output Format
Return ONLY the updated JSON for the "tree" and "vision" sections.
```json
{{
  "vision": {{ ... }},
  "tree": [ ... ]
}}
```
