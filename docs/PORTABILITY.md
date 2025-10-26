# Portability Guide

How to use CloudTasks design patterns in new projects.

## What to Migrate

### 1. Design Guide
**Copy:** `docs/DESIGN_GUIDE.md`

- **Adapt:** Adjust architecture layers if different (React, Django, etc.)
- **Modify:** Update file structure to match your project
- **Keep:** Docstring style and documentation philosophy (universal)

**What's portable:**
- ✅ Docstring principles and examples
- ✅ Documentation philosophy (avoid status docs)
- ✅ Single responsibility principle
- ✅ Naming conventions
- ✅ Code organization principles

**What to adapt:**
- ⚠️ Layer structure (if using different framework)
- ⚠️ Folder layout (if different organization)
- ⚠️ Technology stack references

### 2. Cursor Rules
**Copy:** `.cursorrules`

- **Adapt:** Remove CloudTasks-specific references
- **Keep:** Docstring style rules
- **Keep:** Documentation philosophy
- **Keep:** Architecture principles (if applicable)

**Quick migration:**
1. Copy `.cursorrules` to new project
2. Replace "CloudTasks" with your project name
3. Update paths (keep references to docs/ if you use same structure)
4. Remove CloudTasks-specific examples

### 3. Documentation Philosophy
**Apply these rules:**

**In `/docs/`:**
- Only permanent reference documentation
- README.md (setup/quick start)
- DESIGN_GUIDE.md (architecture and patterns)
- API_CONTRACTS.md (if you have APIs)
- Configuration guides (if complex)
- Developer guides (if helpful)

**In `/plans/`:**
- Active work plans
- Delete when complete
- Temporary during development

**Never create:**
- "PROGRESS", "COMPLETE", "SUMMARY" docs
- Status update documents
- "What changed" logs

### 4. Folder Structure Template

```
src/
  core/           # Domain logic (adapt to your needs)
  services/       # Business logic
  models/         # Data models
  utils/          # Shared utilities
  [your_other_dirs]/

docs/             # Permanent reference only
plans/            # Active work (delete when done)
tests/            # Test suite
```

## Quick Start Checklist

- [ ] Copy `docs/DESIGN_GUIDE.md` to new project
- [ ] Copy `.cursorrules` to new project
- [ ] Update `.cursorrules` with your project name
- [ ] Adapt DESIGN_GUIDE.md folder structure to your project
- [ ] Create README.md with setup instructions
- [ ] Set up `/docs/` and `/plans/` folders
- [ ] Apply docstring style from day one

## Core Principles That Never Change

1. **Brief docstrings**: Help understand WHAT, not HOW
2. **Single responsibility**: One class per file
3. **Layered architecture**: Clear separation of concerns
4. **Minimal docs**: Only what matters in 6+ months
5. **Active work in plans**: Delete when complete
6. **Permanent docs in docs**: Keep minimal and valuable

## Example Migration

**Old CloudTasks:**
```python
# In .cursorrules
Read docs/DESIGN_GUIDE.md for architecture and patterns.
```

**New Project:**
```python
# In .cursorrules
Read docs/DESIGN_GUIDE.md for architecture and patterns.
```

**No change needed** - the reference still works if you keep the same structure.

## Common Adaptations

**If using Django:**
- Services → Business logic in views or separate services
- Core → Domain logic in model methods or managers
- Templates already at project root

**If using React:**
- Services → API client layer
- Core → Business logic hooks/services
- Templates → Components in src/components/

**If using FastAPI:**
- Services → Business logic in route handlers or services
- Core → Domain logic in separate modules
- Templates → HTML templates if using

The key is maintaining the separation of concerns regardless of framework.

## Summary

**Migrate:**
- Design principles (docstrings, organization)
- Documentation philosophy
- Architecture patterns (adapt to your stack)
- Cursor rules (update context)

**Don't migrate:**
- CloudTasks-specific implementation details
- Technology-specific code examples
- Project-specific folder structures

The philosophy and patterns are universal. The implementation is project-specific.

