FROM python:3.7.5

WORKDIR /app

COPY requirements.txt /app

RUN apt-get update && apt-get install ffmpeg libsm6 libxext6 -y

RUN pip install -r requirements.txt

COPY . /app

#CMD ls
CMD ["python","app.py"]
