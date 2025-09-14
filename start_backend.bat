cd .\.venv\Scripts\
call activate
cd ..
cd ..
cd .\backend\
python manage.py runserver 0.0.0.0:8000
pause 