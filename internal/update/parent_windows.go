//go:build windows

package update

import (
	"errors"
	"fmt"
	"golang.org/x/sys/windows"
	"os"
	"path/filepath"
	"strings"
	"time"
	"unsafe"
)

func waitParent(pid int, timeout time.Duration) error {
	if pid <= 0 {
		return fmt.Errorf("processo pai inválido")
	}
	h, e := windows.OpenProcess(windows.SYNCHRONIZE, false, uint32(pid))
	if e == windows.ERROR_INVALID_PARAMETER {
		return nil
	}
	if e != nil {
		return e
	}
	defer windows.CloseHandle(h)
	status, e := windows.WaitForSingleObject(h, uint32(timeout.Milliseconds()))
	if e != nil {
		return e
	}
	if status != windows.WAIT_OBJECT_0 {
		return fmt.Errorf("aplicativo ainda em execução")
	}
	return nil
}

type installProcess struct {
	pid  uint32
	name string
	path string
}

// prepareInstallDirectory waits for the packaged WebView2 process group to
// release its files. A WebView2 process can outlive the Wails host briefly;
// after a short grace period, only the runtime shipped inside this install is
// stopped. Other app processes are allowed to exit naturally.
func prepareInstallDirectory(target string) error {
	runtimeDir := filepath.Join(target, "bin", "webview2")
	if err := waitForProcessesInDirectory(runtimeDir, 3*time.Second); err != nil {
		if stopErr := stopBundledWebViewProcesses(runtimeDir); stopErr != nil {
			return fmt.Errorf("não foi possível encerrar o WebView2 empacotado: %w", stopErr)
		}
	}
	return waitForProcessesInDirectory(target, 60*time.Second)
}

func waitForProcessesInDirectory(dir string, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	for {
		processes, err := processesInDirectory(dir)
		if err != nil {
			return err
		}
		if len(processes) == 0 {
			return nil
		}
		if !time.Now().Before(deadline) {
			return fmt.Errorf("processos ainda usam a pasta %s: %s", dir, describeInstallProcesses(processes))
		}
		time.Sleep(200 * time.Millisecond)
	}
}

func processesInDirectory(dir string) ([]installProcess, error) {
	snapshot, err := windows.CreateToolhelp32Snapshot(windows.TH32CS_SNAPPROCESS, 0)
	if err != nil {
		return nil, fmt.Errorf("não foi possível listar processos do Windows: %w", err)
	}
	defer windows.CloseHandle(snapshot)

	entry := windows.ProcessEntry32{Size: uint32(unsafe.Sizeof(windows.ProcessEntry32{}))}
	err = windows.Process32First(snapshot, &entry)
	if errors.Is(err, windows.ERROR_NO_MORE_FILES) {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("não foi possível ler a lista de processos do Windows: %w", err)
	}

	var matches []installProcess
	for {
		pid := entry.ProcessID
		if pid != 0 && pid != uint32(os.Getpid()) {
			process, found := processImage(pid, entry.ExeFile[:])
			if found && pathIsWithin(dir, process.path) {
				matches = append(matches, process)
			}
		}
		err = windows.Process32Next(snapshot, &entry)
		if errors.Is(err, windows.ERROR_NO_MORE_FILES) {
			break
		}
		if err != nil {
			return nil, fmt.Errorf("não foi possível continuar a leitura dos processos do Windows: %w", err)
		}
	}
	return matches, nil
}

func processImage(pid uint32, executableName []uint16) (installProcess, bool) {
	handle, err := windows.OpenProcess(windows.PROCESS_QUERY_LIMITED_INFORMATION, false, pid)
	if err != nil {
		// Processes can exit between the snapshot and OpenProcess, and protected
		// system processes do not expose their image path to ordinary users.
		return installProcess{}, false
	}
	defer windows.CloseHandle(handle)

	image := make([]uint16, windows.MAX_LONG_PATH)
	size := uint32(len(image))
	if err := windows.QueryFullProcessImageName(handle, 0, &image[0], &size); err != nil {
		return installProcess{}, false
	}
	return installProcess{pid: pid, name: windows.UTF16ToString(executableName), path: windows.UTF16ToString(image[:size])}, true
}

func pathIsWithin(dir, path string) bool {
	root := strings.ToLower(filepath.Clean(dir))
	if !strings.HasSuffix(root, `\`) {
		root += `\`
	}
	return strings.HasPrefix(strings.ToLower(filepath.Clean(path)), root)
}

func describeInstallProcesses(processes []installProcess) string {
	details := make([]string, 0, len(processes))
	for _, process := range processes {
		details = append(details, fmt.Sprintf("%s (PID %d)", process.name, process.pid))
	}
	return strings.Join(details, ", ")
}

func stopBundledWebViewProcesses(runtimeDir string) error {
	processes, err := processesInDirectory(runtimeDir)
	if err != nil {
		return err
	}
	for _, process := range processes {
		if !strings.EqualFold(process.name, "msedgewebview2.exe") {
			continue
		}
		handle, err := windows.OpenProcess(windows.PROCESS_TERMINATE|windows.SYNCHRONIZE, false, process.pid)
		if errors.Is(err, windows.ERROR_INVALID_PARAMETER) {
			continue
		}
		if err != nil {
			return fmt.Errorf("não foi possível encerrar %s (PID %d): %w", process.name, process.pid, err)
		}
		if err := windows.TerminateProcess(handle, 1); err != nil && !errors.Is(err, windows.ERROR_INVALID_PARAMETER) {
			windows.CloseHandle(handle)
			return fmt.Errorf("não foi possível encerrar %s (PID %d): %w", process.name, process.pid, err)
		}
		status, waitErr := windows.WaitForSingleObject(handle, 5000)
		windows.CloseHandle(handle)
		if waitErr != nil {
			return fmt.Errorf("não foi possível aguardar %s (PID %d): %w", process.name, process.pid, waitErr)
		}
		if status != windows.WAIT_OBJECT_0 {
			return fmt.Errorf("o processo %s (PID %d) não encerrou", process.name, process.pid)
		}
	}
	return nil
}
