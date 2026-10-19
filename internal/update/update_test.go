package update

import (
	"archive/zip"
	"os"
	"path/filepath"
	"testing"
)

func TestVersionComparison(t *testing.T) {
	for _, v := range []struct {
		a, b string
		want bool
	}{{"v3.0.0", "3.0.0-dev", true}, {"3.0.1", "3.0.0", true}, {"2.9.9", "3.0.0", false}, {"3.0.0", "3.0.0", false}, {"4.0.0", "3.9.9", true}} {
		if Newer(v.a, v.b) != v.want {
			t.Fatalf("%s %s", v.a, v.b)
		}
	}
}
func TestStageRejectsTraversal(t *testing.T) {
	for _, name := range []string{"../outside", "dir/../../outside"} {
		dir := t.TempDir()
		file := filepath.Join(dir, "package.zip")
		f, _ := os.Create(file)
		z := zip.NewWriter(f)
		w, _ := z.Create(name)
		w.Write([]byte("evil"))
		z.Close()
		f.Close()
		if Stage(file, filepath.Join(dir, "staged")) == nil {
			t.Fatalf("accepted %s", name)
		}
		if _, e := os.Stat(filepath.Join(dir, "outside")); !os.IsNotExist(e) {
			t.Fatal("escaped extraction directory")
		}
	}
}
