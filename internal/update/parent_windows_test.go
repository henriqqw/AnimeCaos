//go:build windows

package update

import (
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"testing"
	"time"
)

func TestWaitForInstallProcessesTracksBundledChild(t *testing.T) {
	if ready := os.Getenv("ANIMECAOS_UPDATE_CHILD_READY"); ready != "" {
		if err := os.WriteFile(ready, []byte("ready"), 0600); err != nil {
			t.Fatal(err)
		}
		millis, _ := strconv.Atoi(os.Getenv("ANIMECAOS_UPDATE_CHILD_SLEEP_MS"))
		time.Sleep(time.Duration(millis) * time.Millisecond)
		return
	}

	root := t.TempDir()
	runtimeDir := filepath.Join(root, "installed", "bin", "webview2")
	if err := os.MkdirAll(runtimeDir, 0755); err != nil {
		t.Fatal(err)
	}
	child := startInstallProcessForTest(t, filepath.Join(runtimeDir, "webview-test.exe"), 1200)
	started := time.Now()
	if err := waitForProcessesInDirectory(filepath.Join(root, "installed"), 5*time.Second); err != nil {
		t.Fatal(err)
	}
	if elapsed := time.Since(started); elapsed < 800*time.Millisecond {
		t.Fatalf("wait returned before the bundled process exited: %s", elapsed)
	}
	if err := child.Wait(); err != nil {
		t.Fatalf("child process exited with an error: %v", err)
	}
}

func TestStopBundledWebViewProcessesStopsOnlyBundledRuntime(t *testing.T) {
	if ready := os.Getenv("ANIMECAOS_UPDATE_CHILD_READY"); ready != "" {
		if err := os.WriteFile(ready, []byte("ready"), 0600); err != nil {
			t.Fatal(err)
		}
		time.Sleep(30 * time.Second)
		return
	}

	root := t.TempDir()
	runtimeDir := filepath.Join(root, "installed", "bin", "webview2")
	if err := os.MkdirAll(runtimeDir, 0755); err != nil {
		t.Fatal(err)
	}
	child := startInstallProcessForTest(t, filepath.Join(runtimeDir, "msedgewebview2.exe"), 30_000)
	if err := stopBundledWebViewProcesses(runtimeDir); err != nil {
		t.Fatal(err)
	}
	if err := child.Wait(); err == nil {
		t.Fatal("WebView2 child was not stopped")
	}
}

func startInstallProcessForTest(t *testing.T, destination string, sleepMillis int) *exec.Cmd {
	t.Helper()
	source, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	input, err := os.Open(source)
	if err != nil {
		t.Fatal(err)
	}
	defer input.Close()
	output, err := os.Create(destination)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := io.Copy(output, input); err != nil {
		output.Close()
		t.Fatal(err)
	}
	if err := output.Close(); err != nil {
		t.Fatal(err)
	}
	ready := filepath.Join(filepath.Dir(destination), fmt.Sprintf("ready-%d", time.Now().UnixNano()))
	command := exec.Command(destination, "-test.run=^TestWaitForInstallProcessesTracksBundledChild$")
	command.Env = append(os.Environ(),
		"ANIMECAOS_UPDATE_CHILD_READY="+ready,
		"ANIMECAOS_UPDATE_CHILD_SLEEP_MS="+strconv.Itoa(sleepMillis),
	)
	if err := command.Start(); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if command.ProcessState == nil {
			_ = command.Process.Kill()
		}
		_ = command.Wait()
	})
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		if _, err := os.Stat(ready); err == nil {
			return command
		}
		time.Sleep(25 * time.Millisecond)
	}
	t.Fatal("child process did not start")
	return nil
}
