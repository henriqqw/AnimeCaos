package providers

import (
	"net/url"
	"regexp"
	"strings"

	"github.com/PuerkitoBio/goquery"
	"github.com/henriqqw/animecaos/internal/netx"
)

const playerRootSelector = `#video_player, .player-container, .video-player, .video-container, .playvideo, .embed-responsive, .video-player-wrapper`
const playerElementSelector = `iframe[src], iframe[data-src], video[src], video[data-src], video source[src], source[src]`

const renderedPlayerInspectScript = `(() => {
  const urls = [];
  const adHost = host => /(^|\.)(t\.dtscout\.com|crwdcntrl\.net|doubleclick\.net|googlesyndication\.com|googleadservices\.com|googletagmanager\.com|google-analytics\.com|adnxs\.com|adsrvr\.org|taboola\.com|outbrain\.com|popads\.net|popcash\.net|waust\.at|21wiz\.com)$/i.test(host || '');
  const add = (element, value) => {
    if (typeof value !== 'string' || !/^https?:\/\//i.test(value.trim())) return;
    try { if (adHost(new URL(value.trim()).hostname)) return; } catch (_) { return; }
    urls.push({url: value.trim(), referrerPolicy: element?.getAttribute?.('referrerpolicy') || element?.referrerPolicy || ''});
  };
  const blocked = /cloudflare|performing security verification|bot detected|verificação de segurança/i.test(document.body?.innerText || '');
  const roots = [...document.querySelectorAll('#video_player,.player-container,.video-player,.video-container,.playvideo,.embed-responsive,.video-player-wrapper')];
  const scopes = roots.length ? roots : [document];
  const adInterstitial = !!document.querySelector('.div-mypopads-protector-iframe,a.mypopads_protector_link,a[href*="/protector/"]');
  const semanticPlayer = element => {
    const marker = [element.id, element.className, element.getAttribute('name'), element.getAttribute('title'), element.getAttribute('data-player'), element.getAttribute('data-role')].filter(Boolean).join(' ');
    return /(^|[-_\s])(player|video|embed|stream|episode)([-_\s]|$)/i.test(marker);
  };
  const advertisingAncestor = element => {
	    let parent = element;
	    for (let depth = 0; parent && depth < 9; depth++, parent = parent.parentElement) {
      const marker = [parent.id, parent.className, parent.getAttribute('aria-label'), parent.title, parent.getAttribute('data-ad'), parent.getAttribute('data-ad-slot')].filter(Boolean).join(' ');
      if (/(^|[-_\s])(ad|ads|advert|advertisement|sponsor|banner|popunder)([-_\s]|$)|mypopads/i.test(marker)) return true;
    }
    return false;
  };
  for (const root of scopes) {
    let elements = [...(root.querySelectorAll?.('iframe[src],iframe[data-src],video[src],video source[src],video[data-src],video,source[src]') || [])].filter(element => !advertisingAncestor(element));
    if (!roots.length && elements.length > 1) {
      const semantic = elements.filter(semanticPlayer);
      elements = semantic.length ? semantic : [];
    }
    for (const element of elements) {
      add(element, element.currentSrc || element.src || element.getAttribute('data-src') || '');
    }
  }
  try {
    if (!blocked && !adInterstitial && typeof window.jwplayer === 'function') {
      const player = window.jwplayer('video_player');
      const item = player?.getPlaylistItem?.();
      add(null, item?.file || '');
      for (const source of item?.sources || []) add(null, source.file || '');
      const config = player?.getConfig?.();
      add(null, config?.file || '');
      for (const source of config?.sources || []) add(null, source.file || '');
      if (!urls.length && player?.play && !window.__animecaosPlayTriggered) {
        window.__animecaosPlayTriggered = true;
        try { player.setMute?.(true); } catch (_) {}
        try { player.play(); } catch (_) {}
      }
    }
  } catch (_) {}
  if (!blocked && !adInterstitial && !urls.length && !window.__animecaosPlayTriggered) {
    const videos = [];
    for (const root of scopes) {
      for (const video of root.querySelectorAll?.('video') || []) {
        if (!advertisingAncestor(video) && (roots.length || semanticPlayer(video))) videos.push(video);
      }
    }
    const video = videos[0];
    if (video) {
      window.__animecaosPlayTriggered = true;
      video.muted = true;
      video.playsInline = true;
      try { const playback = video.play(); playback?.catch?.(() => {}); } catch (_) {}
    }
  }
  const seen = new Set();
  const unique = urls.filter(item => { if (seen.has(item.url)) return false; seen.add(item.url); return true; });
  return {blocked, adInterstitial, urls: unique};
})()`

var advertisingAncestorRE = regexp.MustCompile(`(?i)(?:^|[-_\s])(?:ad|ads|advert|advertisement|sponsor|banner|popunder)(?:$|[-_\s])`)
var playerElementMarkerRE = regexp.MustCompile(`(?i)(?:^|[-_\s])(?:player|video|embed|stream|episode)(?:$|[-_\s])`)

type playerURLCandidate struct {
	URL            string `json:"url"`
	ReferrerPolicy string `json:"referrerPolicy,omitempty"`
}

type renderedPlayerState struct {
	Blocked        bool                 `json:"blocked"`
	AdInterstitial bool                 `json:"adInterstitial"`
	URLs           []playerURLCandidate `json:"urls"`
}

// pagePlayerCandidates prefers known playback containers. A page with an
// explicit player root must not fall back to unrelated iframes elsewhere on
// the document, since those are commonly analytics or advertising frames.
func pagePlayerCandidates(doc *goquery.Document, pageURL string) []playerURLCandidate {
	roots := doc.Find(playerRootSelector)
	scope := doc.Selection
	if roots.Length() > 0 {
		scope = roots
	}
	var candidates []playerURLCandidate
	scope.Find(playerElementSelector).Each(func(_ int, element *goquery.Selection) {
		if hasAdvertisingAncestor(element) {
			return
		}
		raw, _ := element.Attr("src")
		if strings.TrimSpace(raw) == "" {
			raw, _ = element.Attr("data-src")
		}
		if strings.TrimSpace(raw) == "" {
			return
		}
		resolved := scrapedHTTPURL(pageURL, raw)
		if resolved == "" || isAdvertisingURL(resolved) {
			return
		}
		policy, _ := element.Attr("referrerpolicy")
		candidates = append(candidates, playerURLCandidate{URL: resolved, ReferrerPolicy: strings.TrimSpace(policy)})
	})
	if roots.Length() == 0 && len(candidates) > 1 {
		semantic := candidates[:0]
		scope.Find(playerElementSelector).Each(func(_ int, element *goquery.Selection) {
			if hasAdvertisingAncestor(element) || !hasPlayerElementMarker(element) {
				return
			}
			raw := element.AttrOr("src", element.AttrOr("data-src", ""))
			resolved := scrapedHTTPURL(pageURL, raw)
			if resolved == "" || isAdvertisingURL(resolved) {
				return
			}
			semantic = append(semantic, playerURLCandidate{URL: resolved, ReferrerPolicy: strings.TrimSpace(element.AttrOr("referrerpolicy", ""))})
		})
		candidates = semantic
	}
	return uniquePlayerCandidates(candidates)
}

func hasPlayerRoot(doc *goquery.Document) bool {
	return doc.Find(playerRootSelector).Length() > 0
}

func hasAdvertisingAncestor(element *goquery.Selection) bool {
	for parent, depth := element, 0; parent.Length() > 0 && depth < 9; parent, depth = parent.Parent(), depth+1 {
		for _, name := range []string{"id", "class", "aria-label", "title", "data-ad", "data-ad-slot"} {
			value, _ := parent.Attr(name)
			value = strings.TrimSpace(value)
			if value == "" {
				continue
			}
			if strings.Contains(strings.ToLower(value), "mypopads") || advertisingAncestorRE.MatchString(value) {
				return true
			}
		}
	}
	return false
}

func hasPlayerElementMarker(element *goquery.Selection) bool {
	for _, name := range []string{"id", "class", "name", "title", "data-player", "data-role"} {
		value := element.AttrOr(name, "")
		if playerElementMarkerRE.MatchString(value) {
			return true
		}
	}
	return false
}

func uniquePlayerCandidates(candidates []playerURLCandidate) []playerURLCandidate {
	seen := make(map[string]bool, len(candidates))
	out := make([]playerURLCandidate, 0, len(candidates))
	for _, candidate := range candidates {
		candidate.URL = strings.TrimSpace(candidate.URL)
		if candidate.URL == "" || seen[candidate.URL] || isAdvertisingURL(candidate.URL) {
			continue
		}
		seen[candidate.URL] = true
		out = append(out, candidate)
	}
	return out
}

// isAdvertisingURL filters known ad and analytics hosts before they can be
// opened as player pages. It deliberately uses host boundaries rather than
// broad path or substring matches so signed media URLs on other hosts survive.
func isAdvertisingURL(raw string) bool {
	return netx.IsAdvertisingURL(raw)
}

func isAdvertisingHost(rawHost string) bool {
	return netx.IsAdvertisingHost(rawHost)
}

// playerReferer models explicit iframe referrer policies. With no policy, keep
// the source-specific Referer behavior already used by the scraper.
func playerReferer(parentURL, candidateURL, policy, fallback string) string {
	parent, parentErr := url.Parse(parentURL)
	child, childErr := url.Parse(candidateURL)
	if parentErr != nil || childErr != nil {
		if strings.EqualFold(strings.TrimSpace(policy), "no-referrer") {
			return ""
		}
		return fallback
	}
	policy = strings.ToLower(strings.TrimSpace(policy))
	sameOrigin := strings.EqualFold(parent.Scheme, child.Scheme) && strings.EqualFold(parent.Host, child.Host)
	origin := parent.Scheme + "://" + parent.Host + "/"
	downgrade := strings.EqualFold(parent.Scheme, "https") && strings.EqualFold(child.Scheme, "http")
	switch policy {
	case "no-referrer":
		return ""
	case "same-origin":
		if sameOrigin {
			return parentURL
		}
		return ""
	case "origin":
		return origin
	case "origin-when-cross-origin":
		if sameOrigin {
			return parentURL
		}
		return origin
	case "strict-origin":
		if downgrade {
			return ""
		}
		return origin
	case "strict-origin-when-cross-origin":
		if downgrade {
			return ""
		}
		if sameOrigin {
			return parentURL
		}
		return origin
	case "no-referrer-when-downgrade", "unsafe-url":
		if downgrade && policy == "no-referrer-when-downgrade" {
			return ""
		}
		return parentURL
	default:
		return fallback
	}
}
