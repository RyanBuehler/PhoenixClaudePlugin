---
name: invoke-windows-agent
description: Specialized assistance for Windows platform C++ development. Use when working with Win32 APIs, Windows handles, COM programming, Windows-specific code, platform liaison modules, DLLs, process management, threading, registry access, or any Windows-specific implementation. Helps write portable platform abstraction layers and Windows-optimized code.
tools: Read, Grep, Glob, Bash, Edit, Write
---

# Windows C++ Development Skill

## Core Principles

1. **Prefer Modern C++ and the Standard Library**: Always prefer `std::thread`, `std::mutex`, `std::filesystem`, `std::chrono`, `std::atomic`, and other standard library facilities over platform-specific APIs. Only use Win32 APIs when the standard library genuinely cannot accomplish the task (e.g., registry access, COM, I/O completion ports, memory-mapped files with specific Windows semantics).
2. **No Exceptions**: Use error codes, `HRESULT`, `GetLastError()`, or result types instead of try/catch/throw
3. **Platform Isolation**: Windows-specific code belongs in dedicated platform liaison modules, not mixed with shared sources. The build system ensures Windows code only compiles on Windows.
4. **No Platform Guards in Shared Code**: Avoid `#ifdef _WIN32` in shared headers; use compile-time module selection instead
5. **Use `#pragma once`**: All headers must use `#pragma once`. Do not use traditional `#ifndef`/`#define`/`#endif` header guards.

## Windows Error Handling Patterns

### Using GetLastError

```cpp
// For Win32 functions that return BOOL, HANDLE, or similar
bool OpenFileExample(const wchar_t* path, HANDLE& outHandle)
{
	outHandle = CreateFileW(
		path,
		GENERIC_READ,
		FILE_SHARE_READ,
		nullptr,
		OPEN_EXISTING,
		FILE_ATTRIBUTE_NORMAL,
		nullptr
	);

	if (outHandle == INVALID_HANDLE_VALUE)
	{
		DWORD error = GetLastError();
		// Log error code and use FormatMessage for description
		return false;
	}
	return true;
}
```

### Using HRESULT

```cpp
// For COM and modern Windows APIs
struct Result
{
	HRESULT hr = S_OK;
	explicit operator bool() const { return SUCCEEDED(hr); }
};

Result InitializeCOM()
{
	HRESULT hr = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
	if (FAILED(hr))
	{
		return {hr};
	}
	return {};
}
```

### Format Error Messages

```cpp
std::wstring GetLastErrorMessage(DWORD errorCode = 0)
{
	if (errorCode == 0)
		errorCode = GetLastError();

	wchar_t* buffer = nullptr;
	DWORD size = FormatMessageW(
		FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
		nullptr,
		errorCode,
		MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
		reinterpret_cast<LPWSTR>(&buffer),
		0,
		nullptr
	);

	std::wstring message;
	if (size > 0 && buffer)
	{
		message.assign(buffer, size);
		LocalFree(buffer);
	}
	return message;
}
```

## RAII for Windows Resources

### Generic Handle Wrapper

```cpp
template<typename HandleType, HandleType InvalidValue>
class ScopedHandle
{
public:
	ScopedHandle() = default;
	explicit ScopedHandle(HandleType handle) : m_handle(handle) {}

	~ScopedHandle()
	{
		Close();
	}

	ScopedHandle(ScopedHandle&& other) : m_handle(other.Release()) {}

	ScopedHandle& operator=(ScopedHandle&& other)
	{
		if (this != &other)
		{
			Close();
			m_handle = other.Release();
		}
		return *this;
	}

	ScopedHandle(const ScopedHandle&) = delete;
	ScopedHandle& operator=(const ScopedHandle&) = delete;

	HandleType Get() const { return m_handle; }
	HandleType* GetAddressOf() { Close(); return &m_handle; }
	explicit operator bool() const { return m_handle != InvalidValue; }

	HandleType Release()
	{
		HandleType h = m_handle;
		m_handle = InvalidValue;
		return h;
	}

	void Close()
	{
		if (m_handle != InvalidValue)
		{
			CloseHandle(m_handle);
			m_handle = InvalidValue;
		}
	}

private:
	HandleType m_handle = InvalidValue;
};

// Common handle types
using WinHandle = ScopedHandle<HANDLE, nullptr>;
using FileHandle = ScopedHandle<HANDLE, INVALID_HANDLE_VALUE>;
```

### Registry Key Wrapper

```cpp
class ScopedRegKey
{
public:
	ScopedRegKey() = default;
	explicit ScopedRegKey(HKEY key) : m_key(key) {}
	~ScopedRegKey() { Close(); }

	ScopedRegKey(ScopedRegKey&& other) : m_key(other.m_key) { other.m_key = nullptr; }
	ScopedRegKey& operator=(ScopedRegKey&& other)
	{
		Close();
		m_key = other.m_key;
		other.m_key = nullptr;
		return *this;
	}

	ScopedRegKey(const ScopedRegKey&) = delete;
	ScopedRegKey& operator=(const ScopedRegKey&) = delete;

	HKEY Get() const { return m_key; }
	HKEY* GetAddressOf() { Close(); return &m_key; }
	explicit operator bool() const { return m_key != nullptr; }

	void Close()
	{
		if (m_key)
		{
			RegCloseKey(m_key);
			m_key = nullptr;
		}
	}

private:
	HKEY m_key = nullptr;
};
```

## Common Windows APIs

### Process Management
- `CreateProcess()` - Start new process
- `OpenProcess()` - Get handle to existing process
- `TerminateProcess()` - End process
- `GetExitCodeProcess()` - Get process exit code
- `WaitForSingleObject()` / `WaitForMultipleObjects()` - Wait for process/thread

### File Operations
- `CreateFile()` / `CreateFileW()` - Open or create file
- `ReadFile()` / `WriteFile()` - Synchronous I/O
- `ReadFileEx()` / `WriteFileEx()` - Asynchronous I/O
- `GetFileSizeEx()` - Get file size
- `CreateFileMapping()` / `MapViewOfFile()` - Memory-mapped files
- `FindFirstFile()` / `FindNextFile()` - Directory enumeration
- `GetFileAttributes()` - File attributes

### Memory Management
- `VirtualAlloc()` / `VirtualFree()` - Virtual memory
- `HeapAlloc()` / `HeapFree()` - Heap memory
- `CreateFileMapping()` / `MapViewOfFile()` - Shared memory

### Threading
- `CreateThread()` - Create thread
- `WaitForSingleObject()` - Wait for thread/event
- `InitializeCriticalSection()` - Critical sections
- `CreateEvent()` / `SetEvent()` - Event objects
- `CreateMutex()` - Mutex objects
- `InitializeSRWLock()` - Slim reader/writer locks
- `InitializeConditionVariable()` - Condition variables

### Synchronization Primitives
- Critical Sections (fast, process-local)
- Mutexes (cross-process capable)
- Events (manual/auto reset)
- Semaphores
- SRW Locks (reader/writer)
- Condition Variables

### Registry
- `RegOpenKeyEx()` / `RegCreateKeyEx()` - Open/create keys
- `RegQueryValueEx()` - Read values
- `RegSetValueEx()` - Write values
- `RegDeleteKey()` / `RegDeleteValue()` - Delete keys/values
- `RegEnumKeyEx()` / `RegEnumValue()` - Enumerate

### DLL Management
- `LoadLibrary()` / `LoadLibraryEx()` - Load DLL
- `GetProcAddress()` - Get function pointer
- `FreeLibrary()` - Unload DLL
- `GetModuleHandle()` - Get loaded module

### Networking (Winsock)
- `WSAStartup()` / `WSACleanup()` - Initialize Winsock
- `socket()` / `closesocket()` - Socket operations
- `WSAGetLastError()` - Get socket error

## Platform Liaison Architecture

When adding Windows-specific functionality:

1. **Define abstract interface** in shared code:
```cpp
// Shared/IPlatformFile.h
class IPlatformFile
{
public:
	virtual ~IPlatformFile() = default;
	virtual bool Open(const wchar_t* path) = 0;
	virtual size_t Read(void* buffer, size_t size) = 0;
	virtual void Close() = 0;
};
```

2. **Implement in platform module**:
```cpp
// WindowsLiaison/WindowsFile.cpp
class WindowsFile : public IPlatformFile
{
	// Windows-specific implementation using Win32 APIs
};
```

3. **Register via factory or compile-time selection**

## Unicode Considerations

- **Always use wide strings** (`wchar_t*`, `std::wstring`) for Windows APIs
- Use `W` suffix functions: `CreateFileW`, `LoadLibraryW`, etc.
- Define `UNICODE` and `_UNICODE` in project settings
- Convert UTF-8 to UTF-16: `MultiByteToWideChar(CP_UTF8, ...)`
- Convert UTF-16 to UTF-8: `WideCharToMultiByte(CP_UTF8, ...)`

```cpp
std::wstring Utf8ToWide(const char* utf8)
{
	if (!utf8 || !*utf8)
		return {};

	int size = MultiByteToWideChar(CP_UTF8, 0, utf8, -1, nullptr, 0);
	if (size <= 0)
		return {};

	std::wstring result(size - 1, L'\0');
	MultiByteToWideChar(CP_UTF8, 0, utf8, -1, result.data(), size);
	return result;
}

std::string WideToUtf8(const wchar_t* wide)
{
	if (!wide || !*wide)
		return {};

	int size = WideCharToMultiByte(CP_UTF8, 0, wide, -1, nullptr, 0, nullptr, nullptr);
	if (size <= 0)
		return {};

	std::string result(size - 1, '\0');
	WideCharToMultiByte(CP_UTF8, 0, wide, -1, result.data(), size, nullptr, nullptr);
	return result;
}
```

## COM Programming

### COM Initialization RAII

```cpp
class ComScope
{
public:
	ComScope(DWORD coinit = COINIT_MULTITHREADED)
		: m_initialized(SUCCEEDED(CoInitializeEx(nullptr, coinit)))
	{
	}

	~ComScope()
	{
		if (m_initialized)
			CoUninitialize();
	}

	ComScope(const ComScope&) = delete;
	ComScope& operator=(const ComScope&) = delete;

	explicit operator bool() const { return m_initialized; }

private:
	bool m_initialized;
};
```

### Smart Pointer for COM

```cpp
template<typename T>
class ComPtr
{
public:
	ComPtr() = default;
	~ComPtr() { Release(); }

	ComPtr(const ComPtr& other) : m_ptr(other.m_ptr) { if (m_ptr) m_ptr->AddRef(); }
	ComPtr(ComPtr&& other) : m_ptr(other.m_ptr) { other.m_ptr = nullptr; }

	ComPtr& operator=(const ComPtr& other)
	{
		if (m_ptr != other.m_ptr)
		{
			Release();
			m_ptr = other.m_ptr;
			if (m_ptr) m_ptr->AddRef();
		}
		return *this;
	}

	ComPtr& operator=(ComPtr&& other)
	{
		if (this != &other)
		{
			Release();
			m_ptr = other.m_ptr;
			other.m_ptr = nullptr;
		}
		return *this;
	}

	T* Get() const { return m_ptr; }
	T** GetAddressOf() { Release(); return &m_ptr; }
	T* operator->() const { return m_ptr; }
	explicit operator bool() const { return m_ptr != nullptr; }

	void Release()
	{
		if (m_ptr)
		{
			m_ptr->Release();
			m_ptr = nullptr;
		}
	}

private:
	T* m_ptr = nullptr;
};
```

## Debugging and Profiling

### Useful Tools
- **Visual Studio Debugger** - Full-featured debugging
- **WinDbg** - Low-level Windows debugging
- **Process Monitor** - File/registry/network monitoring
- **Process Explorer** - Enhanced task manager
- **Dependency Walker** - DLL dependency analysis
- **API Monitor** - API call tracing
- **Performance Monitor** - System performance

### Debug Output

```cpp
void DebugLog(const wchar_t* format, ...)
{
	wchar_t buffer[1024];
	va_list args;
	va_start(args, format);
	vswprintf_s(buffer, format, args);
	va_end(args);
	OutputDebugStringW(buffer);
}
```

## Build Considerations

### Compiler Flags
- `/DUNICODE /D_UNICODE` - Unicode support
- `/EHs-c-` - Disable exceptions
- Link libraries: `kernel32.lib`, `user32.lib`, `advapi32.lib`, etc.

### CMake Patterns
```cmake
if(WIN32)
	target_sources(MyLib PRIVATE
		${CMAKE_CURRENT_SOURCE_DIR}/WindowsLiaison/Implementation.cpp
	)
	target_link_libraries(MyLib PRIVATE kernel32 user32 advapi32)
	target_compile_definitions(MyLib PRIVATE UNICODE _UNICODE)
endif()
```

## Common Pitfalls

1. **Forgetting to check return values** - Always check BOOL returns and HRESULT
2. **Handle leaks** - Use RAII wrappers for all handles
3. **ANSI vs Unicode** - Always use W-suffix functions
4. **GetLastError timing** - Call immediately after failed function, before any other API
5. **COM initialization** - Must init COM on each thread that uses it
6. **DLL search order** - Be aware of DLL hijacking risks
7. **Buffer sizes** - Windows often uses character counts, not byte counts

## Memory Ordering Comments

When using atomics, always document the ordering choice:
```cpp
// Release: ensures all prior writes are visible before this store
m_ready.store(true, std::memory_order_release);

// Acquire: ensures all subsequent reads see writes before the release
if (m_ready.load(std::memory_order_acquire))
{
	// Safe to read shared data
}
```