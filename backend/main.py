import os
import sys
from pathlib import Path

curr_dir = Path(__file__).resolve().parent
if str(curr_dir) not in sys.path:
    sys.path.insert(0, str(curr_dir))

from app.main import app, create_application  # noqa: F401

if __name__ == '__main__':
    import uvicorn

    port = int(os.getenv('PORT', 10000))
    print(f'[RENDER] Starting Uvicorn on 0.0.0.0:{port}...')
    uvicorn.run('app.main:app', host='0.0.0.0', port=port)
