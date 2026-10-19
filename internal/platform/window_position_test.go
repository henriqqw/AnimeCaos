package platform

import "testing"

func TestWindowPositionIntersectsWorkArea(t *testing.T) {
	area := workArea{left: 0, top: 0, right: 1600, bottom: 860}
	tests := []struct {
		name                string
		x, y, width, height int
		area                workArea
		want                bool
	}{
		{name: "inside primary monitor", x: 60, y: 30, width: 1460, height: 800, area: area, want: true},
		{name: "inside left monitor with negative coordinates", x: -1400, y: -350, width: 1200, height: 700, area: workArea{left: -1440, top: -372, right: 0, bottom: 488}, want: true},
		{name: "partially visible title bar", x: -1400, y: 10, width: 1600, height: 700, area: area, want: true},
		{name: "offscreen position on primary monitor", x: -1400, y: 10, width: 1200, height: 700, area: area, want: false},
		{name: "minimized sentinel coordinates", x: -32000, y: -32000, width: 900, height: 600, area: area, want: false},
		{name: "title bar below work area", x: 50, y: 820, width: 900, height: 600, area: area, want: false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := windowPositionIntersectsWorkArea(tt.x, tt.y, tt.width, tt.height, tt.area)
			if got != tt.want {
				t.Fatalf("windowPositionIntersectsWorkArea() = %v, want %v", got, tt.want)
			}
		})
	}
}
