# Skill: Architect
## Description
Designs a 'DeepTree' blueprint for a mathematics textbook, starting from first principles.

## Instructions
- **First Principles**: Define a core 'Vision' for Chapter 1 (Origins), Chapter 2 (Framework), and Chapter 3 (Notation).
- **Structural Integrity**: Design a logical progression for the remaining chapters starting from Chapter 4.
- **Recursive Depth**: For each major chapter, provide 2-4 sub-chapters (Level 2).

## Domain
{domain}

## Output Format
Return ONLY a valid JSON object:
```json
{{
  "vision": {{
    "1.0.0": "...",
    "2.0.0": "...",
    "3.0.0": "..."
  }},
  "tree": [
    {{ "id": "1.0.0", "title": "Origins", "type": "file" }},
    {{ "id": "2.0.0", "title": "Framework", "type": "file" }},
    {{ "id": "3.0.0", "title": "Notation", "type": "file" }},
    {{ 
      "id": "4.0.0", 
      "title": "...", 
      "type": "dir", 
      "children": [
        {{ "id": "4.1", "title": "...", "type": "file" }}
      ] 
    }}
  ]
}}
```
