# Version 1.0 by Щеблыкин Николай Викторович (18.12.2024г.)
import os
import subprocess
import fileinput


nexus_user = ''
nexus_password = ''
nexus_url = ''


def install_tantor(login, password, url):
    # По умолчанию будет установлена v16 Special Edition
    version_db = 2
    jobs = {'Загружаю скрипт установки': 'wget https://public.tantorlabs.ru/db_installer.sh',
            'Делаю скрипт исполняемым': 'chmod +x db_installer.sh'}

    for key, value in jobs.items():
        print(key)
        os.system(value)

    # Получаем информацию о системе
    system_info = os.uname()
    # Имя хоста находится в поле nodename
    hostname = system_info.nodename
    if hostname.startswith('1c'):
        choice_version = input('Вижу hostname сервера начинается на 1С и имеет отношение к ИС связанной с 1С,'
                               'установим v16 Special Edition for 1C? (y/n): ')
        if choice_version.lower() in ('y', 'yes', 'д'):
            version_db = 3
    else:
        print('Начало установки, какую версию устанавливаем? \n'
              '1. v16 BE \n'
              '2. v16 Special Edition \n'
              '3. v16 Special Edition for 1C'
              )
        version_db = int(input())

    export_variables = (
        f'export NEXUS_USER="{login}" && export NEXUS_USER_PASSWORD="{password}" && export NEXUS_URL="{url}"')

    install_scripts = {1: './db_installer.sh --major-version=16 --edition=be',
                       2: './db_installer.sh --major-version=16 --edition=se',
                       3: './db_installer.sh --major-version=16 --edition=se-1c'}
    os.system(f'{export_variables} && {install_scripts[version_db]}')
    return version_db


# path - путь для установки базы
def manage_path(path):
    os.system(f'mkdir -p {path}')
    extracted_path = f"/{path.split('/')[1]}"
    os.system(f'chown -R postgres:postgres {extracted_path}')
    os.system(f'chmod -R 750 {extracted_path}')


# Добавление привилегий если режим ОС Смоленск
def switch_mode_postgres():
    result = subprocess.run(['astra-modeswitch', 'get'], capture_output=True, text=True)
    output = result.stdout
    if output == 2 or '2':
        os.system('pdpl-user postgres -i 63')
        print('Режим ОС: Смоленск')
        print('Уровень привилегий повышен для УЗ: postrges ')


# Редактирование файла сервиса СУБД
def set_bash_postgres(path, version_db):
    directory = '/var/lib/postgresql/'
    filename = ".bash_profile"
    file_path = os.path.join(directory, filename)
    # Проверка существования директории
    if not os.path.exists(directory):
        os.makedirs(directory)
    with open(file_path, 'w') as file:
        file.write("export PATH=/opt/tantor/db/16/bin:$PATH\n")
        file.write(f"export PGDATA={path}/tantor-{version_db}-16/data\n")


# Инициализация БД
def init_db():
    print('Инициализирую базу данных')
    user = 'postgres'
    command = 'initdb -k'
    subprocess.run(['su', '-', user, '-c', command], capture_output=True, text=True)


# Редактирование файла юнита systemd
def set_service(path, version_db):
    file_service = ''
    directory = '/usr/lib/systemd/system/'
    if version_db == 'be':
        file_service = f'tantor-be-server-16.service'
    elif version_db == 'se':
        file_service = f'tantor-se-server-16.service'
    elif version_db == 'se-1c':
        file_service = f'tantor-se-1c-server-16.service'
    file_path = os.path.join(directory, file_service)

    prefix = 'Environment=PGDATA'
    new_line = f'Environment=PGDATA={path}/tantor-{version_db}-16/data'

    for line in fileinput.input(file_path, inplace=True):
        if line.startswith(prefix):
            print(new_line)
        else:
            print(line, end='')  # Записываем строку без изменений
    print("Перезапускаю службу 'systemd'")
    os.system('systemctl daemon-reload')
    service_name = os.path.basename(file_path)
    print('Включаю сервис в автозагрузку')
    os.system(f'systemctl enable {service_name}')
    return service_name

# Расчет shared_buffer для СУБД Tantor
def memory_info():
    print('1. Собираю информацию о системе...')
    # получение из ОС объема ОЗУ
    memory_size = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') // (1024 * 1024 * 1000)
    print(f'ОЗУ: {memory_size} GB')
    # расчет кэша БД исходя из объема ОЗУ
    pg_cache = int((memory_size * 0.25))
    choice_buffer = input(f'shared buffer = {pg_cache} GB? (y/n): ')
    if choice_buffer.lower() in ('y', 'yes', 'д'):  # Проверяем ввод
        return pg_cache
    else:
        pg_cache = int(input('Введите желаемое значение в GB: '))
        return pg_cache



# Перемещение каталога pg_wal
def manage_wal(path ,version_db):
    path_wal = input("Введите путь до каталога 'wal': ")
    os.system(f'mkdir -p {path_wal}/tantor-{version_db}-16') # '-p' рекурсивно
    os.system(f'chown -R postgres:postgres {path_wal}')
    os.system(f'chmod -R 750 {path_wal}')
    os.system(f'mv {path}/tantor-{version_db}-16/data/pg_wal/* {path_wal}/tantor-{version_db}-16')
    os.system(f'rm -rf {path}/tantor-{version_db}-16/data/pg_wal')
    os.system(f'ln -s {path_wal}/tantor-{version_db}-16 {path}/tantor-{version_db}-16/data/pg_wal')
    print("Каталог 'wal' перемещен на отдельную файловую систему")


# Смена пароля postgres в системе и в СУБД
def passwd_postgres(password):
    os.system(f'passwd postgres <<EOF\n{password}\n{password}\nEOF')

    command = f"psql -c \"ALTER USER postgres WITH PASSWORD '{password}';\""
    result = subprocess.run(
        ["su", "-", "postgres", "-c", command],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print("Пароль изменен успешно")
    else:
        print("Ошибка выполнения команды:")
        print(result.stderr)


# Настройка конфига postgresql.conf
def set_conf(path, shared_buffers, version_db):
    file_conf = 'postgresql.conf'
    buffer_db = f'shared_buffers = {shared_buffers}GB			# min 128kB'
    listen = "listen_addresses = '*'			# what IP address(es) to listen on;"
    connections = 'max_connections = 1000			# (change requires restart)'
    tantor_path = f'{path}/tantor-{version_db}-16/data'
    file_path = os.path.join(path, tantor_path, file_conf)

    for line in fileinput.input(file_path, inplace=True):
        if line.startswith('shared_buffers'):
            print(buffer_db)  # Записываем новую строку
        elif line.startswith('#listen_addresses'):
            print(listen)  # Записываем новую строку
        elif line.startswith('max_connections'):
            print(connections)  # Записываем новую строку
        else:
            print(line, end='')  # Записываем строку без изменений
    os.system(f'chown -R postgres:postgres {file_path}')
    return tantor_path


# Настройка конфига pg_hba.conf
def set_pg_hba(path, ip_user):
    file_conf = 'pg_hba.conf'
    file_path = os.path.join(path, file_conf)
    host = f"host    all             all             {ip_user}/32         md5\n"
    # Открываем файл в режиме дозаписи ('a')
    with open(file_path, 'a', encoding='utf-8') as file:
        file.write(host)

# Перезапуск службы Tantor
def restart_tantor(service):
    os.system(f'systemctl stop {service}')
    os.system(f'systemctl start {service}')

def status_tantor(service):
    os.system(f'systemctl status {service}')


if __name__ == '__main__':
    tantor = {
        1: 'be',
        2: 'se',
        3: 'se-1c'
    }
    current_service = ''
    # 1. Установка СУБД Tantor
    version_base = install_tantor(nexus_user, nexus_password, nexus_url)
    # 2. Добавление привилегий если режим ОС Смоленск
    switch_mode_postgres()
    # 3. Запрос пути установки БД
    path_db = input('Укажите путь установки базы данных:\nВида: /data/db\n')
    # 4. Создание каталогов
    manage_path(path_db)
    # 5. Настройка переменных окружения postgres
    set_bash_postgres(path_db, tantor[version_base])
    # 6. Инициализация БД
    init_db()
    # 7. Редактирование файла юнита systemd
    service_unit = set_service(path_db, tantor[version_base])
    # 8. Запрос на перемещение pg_wal в отдельную файловую систему
    wal_choice = input('Перемещать каталог pg_wal на отдельную файловую систему? (y/n)\n')
    if wal_choice.lower() in ('y', 'yes', 'д'):  # Проверяем ввод
        manage_wal(path_db, tantor[version_base])
    # 9. Определяем размер кэша БД
    buffer = memory_info()
    # 10. Настройка конфига postgresql.conf
    path_to_base = set_conf(path_db, buffer, tantor[version_base])
    # 11. Настройка конфига pg_hba.conf
    print('Настройка почти завершена.')
    # 12. Перезапуск службы Tantor
    restart_tantor(service_unit)
    # 13. Смена пароля postgres в системе и в СУБД
    pass_postgres = input('Введите пароль для учетной записи postgres: ')
    passwd_postgres(pass_postgres)
    # 14. Добавление пользователей в pg_hba.conf
    add_users = input('Добавить пользователей в pg_hba.conf? (y/n)\n')
    if add_users.lower() in ('y', 'yes', 'д'):
        ip = input('Введите ip адрес: ')
        set_pg_hba(path_to_base, ip)
    # 15. Проверяем статус службы
    status_tantor(service_unit)
    print('*' * 49)
    print('*' * 10, 'Установка завершена успешно', '*' * 10)
    print('*' * 49)
