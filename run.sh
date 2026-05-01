#! /usr/bin/bash
# Launches the python server using gunicorn, for better performance. Recommended way to start the RC car instead of
# straight up launching the .py file. But either way works fine.
gunicorn app:app -k gthread --workers 1 --threads 8