package providers

import (
	"regexp"
	"strconv"
	"strings"
)

type SearchIntent struct {
	BaseTitle string
	Season    int
	Year      int
}

var seasonSuffixPatterns = []*regexp.Regexp{
	regexp.MustCompile(`(?i)^(.*?)\s+(?:season|temporada)\s*(\d+)(?:st|nd|rd|th|ª|a|º)?\s*$`),
	regexp.MustCompile(`(?i)^(.*?)\s+(\d+)(?:st|nd|rd|th|ª|a|º)?\s*(?:season|temporada)\s*$`),
	regexp.MustCompile(`(?i)^(.*?)\s+s(\d+)\s*$`),
	regexp.MustCompile(`^(.*?)\s*第(\d+)期\s*$`),
}

var yearSuffixPattern = regexp.MustCompile(`(?i)^(.+?)(?:\s+|\s*[\(\[])(19\d{2}|20\d{2})[\)\]]?\s*$`)

// InferSearchIntent recognizes explicit season and year suffixes without
// treating them as part of the provider's catalog title. Seasons are retained
// for E1 preflight; years constrain matching so a base-title lookup cannot
// merge a different adaptation.
func InferSearchIntent(query string) SearchIntent {
	query = strings.TrimSpace(query)
	if base, season := inferSeasonSuffix(query); season > 0 {
		return SearchIntent{BaseTitle: base, Season: season}
	}
	if match := yearSuffixPattern.FindStringSubmatch(query); len(match) == 3 {
		base := strings.TrimRight(strings.TrimSpace(match[1]), " :.–—-_")
		year, err := strconv.Atoi(match[2])
		if err == nil && base != "" {
			if seasonBase, season := inferSeasonSuffix(base); season > 0 {
				return SearchIntent{BaseTitle: seasonBase, Season: season, Year: year}
			}
			return SearchIntent{BaseTitle: base, Year: year}
		}
	}
	return SearchIntent{}
}

func inferSeasonSuffix(query string) (string, int) {
	for _, pattern := range seasonSuffixPatterns {
		match := pattern.FindStringSubmatch(query)
		if len(match) != 3 {
			continue
		}
		season, err := strconv.Atoi(match[2])
		base := strings.TrimRight(strings.TrimSpace(match[1]), " :.–—-_")
		if err == nil && season > 0 && strings.TrimSpace(base) != "" {
			return base, season
		}
	}
	return "", 0
}
