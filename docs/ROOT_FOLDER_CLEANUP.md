# Root Folder Cleanup

## Summary
Cleaned up root directory by organizing scattered files into appropriate locations.

## Files Moved

### Debug Scripts → `src/scripts/`
- `debug_house_tasks.py` - Debug script for checking House category tasks
- `delete_old_tasks.py` - Script to delete old tasks without presented_at field

These are now with other utility scripts in `src/scripts/` directory.

## Files Kept in Root

### Application Entry Points
- `main.py` - App Engine entry point (used by run.bat)
- `app.py` - Flask application factory

### Configuration Files
- `app.yaml` - App Engine configuration
- `requirements.txt` - Python dependencies
- `config/` - Environment-specific configs

### Documentation
- `README.md` - Main project documentation
- `TODO.md` - Project todo list
- `docs/` - Additional documentation

### Development Scripts (.bat files)
- `run.bat` - Start local development server
- `install.bat` - Install dependencies
- `test.bat` - Run tests
- `view_logs.bat` - GCloud log viewer (interactive)
- `tail_logs.bat` - Stream logs in real-time
- `simple_logs.bat` - Show recent logs
- `setup_gcloud_path.bat` - Setup Google Cloud SDK path

### Test Files
- `tests/` - Test suite

### Other Directories
- `src/` - Source code
- `templates/` - HTML templates
- `static/` - Static assets
- `plans/` - Project planning documents

## Rationale

### Why Keep .bat Files in Root?
- Windows-specific convenience scripts
- Referenced in README.md
- Used frequently during development
- Keep root directory simple for Windows users

### Why Keep main.py?
- App Engine entry point requirement
- Referenced by run.bat
- Standard pattern for Flask apps on App Engine

### Why Move Debug Scripts?
- Better organization
- Consistent with other utility scripts
- Easier to find and maintain
- Reduces clutter in root directory

## Future Consideration

### Possible Consolidation
- Create `scripts/` folder for all batch files (not just Python)
- Move .bat files to `scripts/windows/` or similar
- Document Windows vs Unix compatibility

### Benefits of Current Structure
- Simple, flat structure for Windows users
- Easy to find common files
- Follows typical Python project layout
- Clear separation of concerns

## Completed Actions
1. ✅ Moved `debug_house_tasks.py` to `src/scripts/`
2. ✅ Moved `delete_old_tasks.py` to `src/scripts/`
3. ✅ Updated documentation

## Files Remaining in Root
All remaining files serve specific purposes:
- Application entry points
- Configuration files
- Development convenience scripts
- Documentation

No further cleanup needed.

