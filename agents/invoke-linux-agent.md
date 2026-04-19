---
name: invoke-linux-agent
description: Specialized assistance for Linux platform C++ development. Use when working with POSIX APIs, system calls, Linux-specific code, platform liaison modules, shared libraries, process management, threading, file descriptors, signals, memory mapping, or any Linux-specific implementation. Helps write portable platform abstraction layers and Linux-optimized code.
tools: Read, Grep, Glob, Bash, Edit, Write
---

# Linux C++ Development Skill

## Project Style

Before writing or modifying any C++ in this repository, read `references/code-style.md` and the
"Code Guidelines" + "Code Style" sections of the project root `CLAUDE.md`. They define the
enforced conventions for namespaces (no anonymous, no "Detail", purpose-named with collision
checks), return-value handling (no `(void)` discards on error-bearing types — log via Scribe
instead), `auto` usage (forbidden except for unwriteable types like iterators/lambdas; never
on `expected`/`optional`), blank lines after closing braces, naming, and the
formatting/lint toolchain. Code that violates them will fail review.

## Core Principles

1. **Prefer Modern C++ and the Standard Library**: Always prefer `std::thread`, `std::mutex`, `std::filesystem`, `std::chrono`, `std::atomic`, and other standard library facilities over platform-specific APIs. Only use POSIX/Linux APIs when the standard library genuinely cannot accomplish the task (e.g., `epoll`, `mmap` for memory-mapped I/O, `signalfd`, `inotify`).
2. **No Exceptions**: Use error codes, `std::expected`, `std::optional`, or result types instead of try/catch/throw
3. **Platform Isolation**: Linux-specific code belongs in dedicated platform liaison modules, not mixed with shared sources. The build system ensures Linux code only compiles on Linux.
4. **No Platform Guards in Shared Code**: Avoid `#ifdef __linux__` in shared headers; use compile-time module selection instead
5. **Use `#pragma once`**: All headers must use `#pragma once`. Do not use traditional `#ifndef`/`#define`/`#endif` header guards.

## Linux System Programming Patterns

### Error Handling Without Exceptions

```cpp
// Preferred: Return error codes or result types
struct Result
{
	int errorCode = 0;
	std::string_view errorMessage;
	explicit operator bool() const { return errorCode == 0; }
};

Result OpenFile(const char* path, int& outFd)
{
	outFd = open(path, O_RDONLY);
	if (outFd == -1)
	{
		return {errno, strerror(errno)};
	}
	return {};
}
```

### RAII for System Resources

```cpp
// File descriptor wrapper
class FileDescriptor
{
public:
	explicit FileDescriptor(int fd = -1) : m_fd(fd) {}
	~FileDescriptor() { if (m_fd >= 0) close(m_fd); }

	FileDescriptor(FileDescriptor&& other) : m_fd(other.m_fd) { other.m_fd = -1; }
	FileDescriptor& operator=(FileDescriptor&& other)
	{
		if (this != &other)
		{
			if (m_fd >= 0) close(m_fd);
			m_fd = other.m_fd;
			other.m_fd = -1;
		}
		return *this;
	}

	FileDescriptor(const FileDescriptor&) = delete;
	FileDescriptor& operator=(const FileDescriptor&) = delete;

	int Get() const { return m_fd; }
	int Release() { int fd = m_fd; m_fd = -1; return fd; }
	explicit operator bool() const { return m_fd >= 0; }

private:
	int m_fd;
};
```

### Memory Mapping

```cpp
class MappedMemory
{
public:
	MappedMemory() = default;
	~MappedMemory() { Unmap(); }

	bool Map(int fd, size_t length, int prot = PROT_READ, int flags = MAP_PRIVATE)
	{
		Unmap();
		void* ptr = mmap(nullptr, length, prot, flags, fd, 0);
		if (ptr == MAP_FAILED)
			return false;
		m_ptr = ptr;
		m_length = length;
		return true;
	}

	void Unmap()
	{
		if (m_ptr)
		{
			munmap(m_ptr, m_length);
			m_ptr = nullptr;
			m_length = 0;
		}
	}

	void* Data() { return m_ptr; }
	size_t Size() const { return m_length; }

private:
	void* m_ptr = nullptr;
	size_t m_length = 0;
};
```

## Common Linux APIs

### Process Management
- `fork()`, `exec*()`, `waitpid()` - Process creation and control
- `getpid()`, `getppid()` - Process identification
- `prctl()` - Process control operations
- `clone()` - Low-level process/thread creation

### File Operations
- `open()`, `close()`, `read()`, `write()` - Basic I/O
- `pread()`, `pwrite()` - Positional I/O (thread-safe)
- `openat()`, `*at()` family - Directory-relative operations
- `dup()`, `dup2()` - File descriptor duplication
- `fcntl()` - File control operations
- `ioctl()` - Device control
- `inotify_*()` - File system monitoring
- `eventfd()`, `timerfd_*()`, `signalfd()` - Special file descriptors

### Memory Management
- `mmap()`, `munmap()` - Memory mapping
- `mprotect()` - Memory protection
- `mlock()`, `munlock()` - Memory locking
- `posix_memalign()`, `aligned_alloc()` - Aligned allocation

### Threading (prefer pthreads or std::thread)
- `pthread_create()`, `pthread_join()` - Thread management
- `pthread_mutex_*()` - Mutexes
- `pthread_cond_*()` - Condition variables
- `pthread_rwlock_*()` - Read-write locks
- Futex operations for low-level synchronization

### Networking
- `socket()`, `bind()`, `listen()`, `accept()` - Socket basics
- `connect()`, `send()`, `recv()` - Connection operations
- `epoll_*()` - Event polling (preferred over select/poll)
- `getaddrinfo()` - Address resolution

### Signals
- `sigaction()` - Signal handling (prefer over `signal()`)
- `sigprocmask()` - Signal blocking
- `signalfd()` - Signal as file descriptor

## Platform Liaison Architecture

When adding Linux-specific functionality:

1. **Define abstract interface** in shared code:
```cpp
// Shared/IPlatformFile.h
class IPlatformFile
{
public:
	virtual ~IPlatformFile() = default;
	virtual bool Open(const char* path) = 0;
	virtual size_t Read(void* buffer, size_t size) = 0;
	virtual void Close() = 0;
};
```

2. **Implement in platform module**:
```cpp
// LinuxLiaison/LinuxFile.cpp
class LinuxFile : public IPlatformFile
{
	// Linux-specific implementation using system calls
};
```

3. **Register via factory or compile-time selection**

## Debugging and Profiling

### Useful Tools
- `strace` - Trace system calls
- `ltrace` - Trace library calls
- `perf` - Performance analysis
- `valgrind` - Memory debugging
- `gdb` - GNU debugger
- `addr2line` - Address to source mapping

### Debug-Friendly Code
```cpp
// Add meaningful errno context
void LogSystemError(const char* operation)
{
	int savedErrno = errno;
	// Log: operation, savedErrno, strerror(savedErrno)
}
```

## Build Considerations

### Compiler Flags
- `-fPIC` for shared libraries
- `-pthread` for threading
- Link with appropriate libraries: `-lrt`, `-ldl`, `-lpthread`

### CMake Patterns
```cmake
if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
	target_sources(MyLib PRIVATE
		${CMAKE_CURRENT_SOURCE_DIR}/LinuxLiaison/Implementation.cpp
	)
	target_link_libraries(MyLib PRIVATE pthread dl rt)
endif()
```

## Common Pitfalls

1. **Forgetting to check return values** - Always check syscall returns
2. **Signal safety** - Only use async-signal-safe functions in signal handlers
3. **EINTR handling** - Restart interrupted system calls when appropriate
4. **File descriptor leaks** - Use RAII wrappers
5. **Race conditions with fork()** - Be careful with threads and fork
6. **Assuming paths** - Use `/proc/self/exe` for executable path

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