# Используем Ubuntu как базовый образ
FROM ubuntu:22.04

# Устанавливаем необходимые зависимости
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    zlib1g-dev \
    libssl-dev \
    gperf \
    python3 \
    python3-pip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# Клонируем репозиторий Telegram Bot API
RUN git clone --recursive https://github.com/tdlib/telegram-bot-api.git
WORKDIR /app/telegram-bot-api

# Собираем Telegram Bot API
RUN mkdir build && cd build && \
    cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX:PATH=.. .. && \
    cmake --build . --target install

# Создаем директории для данных
RUN mkdir -p /app/telegram-bot-api-data

# Возвращаемся в корневую директорию
WORKDIR /app

# Копируем файлы проекта
COPY . /app/

# Устанавливаем зависимости Python
RUN pip3 install -r requirements.txt

# Команда для запуска будет передаваться через docker-compose