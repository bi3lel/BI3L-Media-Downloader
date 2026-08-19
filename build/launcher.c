#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif

#include <windows.h>
#include <shellapi.h>
#include <wchar.h>

#define APP_TITLE L"BI3L Media Downloader"

static void show_error(const wchar_t *message) {
    MessageBoxW(NULL, message, APP_TITLE, MB_OK | MB_ICONERROR);
}

static BOOL join_path(wchar_t *output, size_t output_count, const wchar_t *directory, const wchar_t *name) {
    int written = swprintf(output, output_count, L"%ls\\%ls", directory, name);
    return written > 0 && (size_t)written < output_count;
}

static BOOL file_exists(const wchar_t *path) {
    DWORD attributes = GetFileAttributesW(path);
    return attributes != INVALID_FILE_ATTRIBUTES && !(attributes & FILE_ATTRIBUTE_DIRECTORY);
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR command_line, int show_command) {
    (void)instance;
    (void)previous;
    (void)command_line;
    (void)show_command;

    wchar_t executable_path[32768];
    DWORD path_length = GetModuleFileNameW(NULL, executable_path, 32768);
    if (path_length == 0 || path_length >= 32768) {
        show_error(L"BI3L Media Downloader could not locate its application folder.");
        return 1;
    }

    wchar_t *last_separator = wcsrchr(executable_path, L'\\');
    if (!last_separator) {
        show_error(L"BI3L Media Downloader could not read its application folder.");
        return 1;
    }
    *last_separator = L'\0';

    wchar_t app_directory[32768];
    wchar_t python_path[32768];
    wchar_t app_path[32768];
    wchar_t setup_path[32768];
    if (!join_path(app_directory, 32768, executable_path, L"App") ||
        !join_path(python_path, 32768, app_directory, L".venv\\Scripts\\pythonw.exe") ||
        !join_path(app_path, 32768, app_directory, L"app.py") ||
        !join_path(setup_path, 32768, app_directory, L"setup.bat")) {
        show_error(L"The BI3L Media Downloader folder path is too long.");
        return 1;
    }

    if (!file_exists(app_path)) {
        show_error(L"app.py is missing. Extract the complete BI3L Media Downloader folder before opening the app.");
        return 1;
    }

    if (file_exists(python_path)) {
        wchar_t launch_command[65536];
        int written = swprintf(launch_command, 65536, L"\"%ls\" \"%ls\"", python_path, app_path);
        if (written <= 0 || written >= 65536) {
            show_error(L"The BI3L Media Downloader launch command is too long.");
            return 1;
        }

        STARTUPINFOW startup = {0};
        PROCESS_INFORMATION process = {0};
        startup.cb = sizeof(startup);
        if (!CreateProcessW(
                NULL,
                launch_command,
                NULL,
                NULL,
                FALSE,
                CREATE_UNICODE_ENVIRONMENT,
                NULL,
                app_directory,
                &startup,
                &process)) {
            show_error(L"BI3L Media Downloader could not start. Run setup.bat and try again.");
            return 1;
        }
        CloseHandle(process.hThread);
        CloseHandle(process.hProcess);
        return 0;
    }

    if (!file_exists(setup_path)) {
        show_error(L"setup.bat is missing. Extract the complete BI3L Media Downloader folder before opening the app.");
        return 1;
    }

    HINSTANCE result = ShellExecuteW(NULL, L"open", setup_path, NULL, app_directory, SW_SHOWNORMAL);
    if ((INT_PTR)result <= 32) {
        show_error(L"Automatic setup could not start. Open setup.bat manually and try again.");
        return 1;
    }
    return 0;
}
