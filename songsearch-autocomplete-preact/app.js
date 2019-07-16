import { Component } from "preact";
import { throttle, debounce } from "throttle-debounce";

const placeholderImage = "/assets/placeholder.png";
const lazyloadThumbnailImage = "/assets/lazyload-thumbnail.png";
// XXX MAKE THIS CONFIGURABLE
const SERVER = "https://songsear.ch";

function absolutifyUrl(uri) {
  if (uri.charAt(0) === "/" && uri.charAt(1) !== "/") {
    return SERVER + uri;
  }
  return uri;
}

// https://coderwall.com/p/i817wa/one-line-function-to-detect-mobile-devices-with-javascript
function isMobileDevice() {
  return (
    typeof window.orientation !== "undefined" ||
    navigator.userAgent.indexOf("IEMobile") !== -1
  );
}

export default class App extends Component {
  state = {
    q: this.props.initialValue || "",
    autocompleteSuggestions: null,
    autocompleteHighlight: -1,
    showAutocompleteSuggestions: true,
    redirectingSearch: false,
    searchMaxLength: null
  };

  componentDidMount() {
    // If the <input> HTML had something typed into it when the React
    // app started, that would be passed to the App when initialized.
    // For example if the React app is slow to load. I.e. async slow.
    const { q } = this.state;
    if (q) {
      this.fetchAutocompleteSuggestions(q);
    }
    if (!isMobileDevice() && !document.location.hash) {
      this.qRef.focus();
    }
  }

  componentWillUnmount() {
    this.dismounted = true;
  }

  submitSearch = event => {
    event.preventDefault();
    this._submit(this.state.q);
  };

  _submit = (submitevent = "enter") => {
    const { q } = this.state;
    if (!q.trim()) {
      return;
    }

    // XXX Perhaps this extra "?autocomplete=${...}" is obsolete!
    let gotoURL = `${SERVER}/q/${encodeURIComponent(
      q
    )}?autocomplete=${submitevent}`;
    this.setState(
      {
        redirectingSearch: true,
        autocompleteSuggestions: null,
        autocompleteHighlight: -1,
        showAutocompleteSuggestions: true
      },
      () => {
        setTimeout(() => {
          if (!this.dismounted) {
            this.setState({ redirectingSearch: false });
          }
        }, 3000);
        document.location.href = gotoURL;
      }
    );
  };

  onFocusSearch = () => {
    if (!this.state.showAutocompleteSuggestions) {
      this.setState({
        showAutocompleteSuggestions: true,
        redirectingSearch: false
      });
    }

    if (!this._firstFocusSearch) {
      this._firstFocusSearch = true;
      // If you're on a small screen this is the first time you've focused,
      // the scroll the top of the search input into view.
      if (window.innerHeight && window.innerHeight < 600) {
        this.qRef.scrollIntoView();
      }
    }
  };

  onBlurSearch = () => {
    setTimeout(() => {
      this.setState({
        showAutocompleteSuggestions: false
      });
    }, 300);
  };

  onChangeSearch = event => {
    const q = event.target.value;
    this.setState({ q }, () => {
      const { q, searchMaxLength } = this.state;
      const length = q.length;
      const maxLength = this.qRef.maxLength;

      if (length > maxLength - 10) {
        this.setState({
          searchMaxLength: [length, maxLength],
          showAutocompleteSuggestions: false
        });
      } else if (searchMaxLength) {
        this.setState({
          searchMaxLength: null,
          showAutocompleteSuggestions: true
        });
      }

      if (q.trim()) {
        if (this.waitingFor) {
          if (q.trim() === this.waitingFor.trim()) {
            // Don't bother, only whitespace has changed.
            return;
          }
        }
        if ((length < 4 || q.endsWith(" ")) && length < 24) {
          // The impatient one.
          this.fetchAutocompleteSuggestionsThrottled(q);
        } else if (length > 24) {
          // The patient one.
          this.fetchAutocompleteSuggestionsDebouncedLong(q);
        } else if (length) {
          // The patient one.
          this.fetchAutocompleteSuggestionsDebounced(q);
        } else {
          this.setState({
            autocompleteSuggestions: null,
            autocompleteSearchSuggestions: null,
            autocompleteHighlight: -1,
            showAutocompleteSuggestions: true,
            redirectingSearch: false
          });
        }
      } else {
        this.setState({
          autocompleteSuggestions: null,
          autocompleteSearchSuggestions: null,
          autocompleteHighlight: -1,
          showAutocompleteSuggestions: true,
          redirectingSearch: false
        });
      }
    });
  };

  fetchAutocompleteSuggestions = q => {
    let url = `${SERVER}/api/search/autocomplete?q=${encodeURIComponent(q)}`;
    const cached = this._fetchAutocompleteSuggestionsCache[q.trim()];
    if (cached) {
      return Promise.resolve(cached).then(results => {
        this.setState({
          autocompleteSuggestions: results.matches,
          autocompleteSearchSuggestions: results.search_suggestions,
          autocompleteHighlight: -1
        });
      });
    }
    this.waitingFor = q;
    fetch(url)
      .then(r => {
        if (r.status === 200) {
          if (q.startsWith(this.waitingFor)) {
            r.json().then(results => {
              this._fetchAutocompleteSuggestionsCache[q.trim()] = results;
              this.setState({
                autocompleteSuggestions: results.matches,
                autocompleteSearchSuggestions: results.search_suggestions,
                autocompleteHighlight: -1
              });
            });
          }
        }
      })
      .catch(ex => {
        console.warn(`Catch fetching ${url} ('${q}'): ${ex.toString()}`);
      });
  };

  fetchAutocompleteSuggestionsDebounced = debounce(
    800,
    this.fetchAutocompleteSuggestions
  );
  fetchAutocompleteSuggestionsDebouncedLong = debounce(
    1800,
    this.fetchAutocompleteSuggestions
  );
  fetchAutocompleteSuggestionsThrottled = throttle(
    1100,
    this.fetchAutocompleteSuggestions
  );

  _fetchAutocompleteSuggestionsCache = {};

  onKeyDownSearch = event => {
    let suggestions = this.state.autocompleteSuggestions;
    if (suggestions) {
      let highlight = this.state.autocompleteHighlight;
      if (
        (event.key === "ArrowDown" || event.key === "Tab") &&
        highlight < suggestions.length
      ) {
        event.preventDefault();
        this.setState({ autocompleteHighlight: highlight + 1 });
      } else if (event.key === "ArrowUp" && highlight > -1) {
        this.setState({ autocompleteHighlight: highlight - 1 });
      } else if (event.key === "Enter") {
        if (highlight > -1) {
          event.preventDefault();
          const searchSuggestions = this.state.autocompleteSearchSuggestions;
          if (highlight === 0 && searchSuggestions && searchSuggestions.total) {
            this._submit("search");
            return;
          }
          highlight--;
          if (suggestions[highlight]._url) {
            this.setState(
              {
                redirectingSearch: true,
                autocompleteSuggestions: null,
                autocompleteHighlight: -1
              },
              () => {
                setTimeout(() => {
                  if (!this.dismounted) {
                    this.setState({ redirectingSearch: false });
                  }
                }, 3000);
                document.location.href = absolutifyUrl(
                  suggestions[highlight]._url
                );
              }
            );
          } else {
            this.setState(
              {
                q: suggestions[highlight].text,
                autocompleteSuggestions: null,
                autocompleteHighlight: -1
              },
              () => this._submit()
            );
          }
        }
      }
    }
  };

  onSelectSuggestion = (event, suggestion) => {
    event.preventDefault();
    if (suggestion._url) {
      this.setState(
        {
          redirectingSearch: true,
          autocompleteSuggestions: null,
          autocompleteHighlight: -1
        },
        () => {
          document.location.href = absolutifyUrl(suggestion._url);
        }
      );
      return;
    }
    let newText = suggestion.text;
    this.setState(
      {
        q: newText,
        autocompleteSuggestions: null,
        autocompleteHighlight: -1
      },
      () => {
        this._submit("clicked");
      }
    );
  };

  onSelectSuggestionAll = event => {
    event.preventDefault();
    this._submit("search");
  };

  render() {
    return (
      <form
        style={{ margin: "50px 0" }}
        action={`${SERVER}/q/`}
        onSubmit={this.submitSearch}
      >
        <div className="ui icon input fluid" style={{ display: "relative" }}>
          <input
            type="search"
            name="term"
            ref={r => (this.qRef = r)}
            maxLength={150}
            value={this.state.q}
            onFocus={this.onFocusSearch}
            onBlur={this.onBlurSearch}
            onInput={this.onChangeSearch}
            onKeyDown={this.onKeyDownSearch}
            className="form-control x-large"
            placeholder="Type your lyrics search here..."
            aria-label="Lyrics search"
          />
          <i className="search icon" onClick={this.onSelectSuggestionAll} />
          {this.state.autocompleteSuggestions &&
          this.state.autocompleteSuggestions.length &&
          this.state.showAutocompleteSuggestions ? (
            <ShowAutocompleteSuggestions
              q={this.state.q}
              onSelectSuggestionAll={this.onSelectSuggestionAll}
              onSelectSuggestion={this.onSelectSuggestion}
              highlight={this.state.autocompleteHighlight}
              suggestions={this.state.autocompleteSuggestions}
              searchSuggestions={this.state.autocompleteSearchSuggestions}
            />
          ) : null}
        </div>
        {this.state.searchMaxLength ? (
          <ShowMaxlengthWarning
            length={this.state.searchMaxLength[0]}
            maxLength={this.state.searchMaxLength[1]}
          />
        ) : null}
        {this.state.redirectingSearch ? (
          <p>
            Sending search to{" "}
            <a href={`${SERVER}/q/${encodeURIComponent(this.state.q)}`}>
              SongSearch
            </a>{" "}
            now...
          </p>
        ) : null}
      </form>
    );
  }
}

function ShowMaxlengthWarning({ length, maxLength }) {
  let className = "help-block maxlength";
  if (length === maxLength) {
    className += " danger";
  }
  return (
    <p className={className}>
      {length} of max {maxLength} characters!
    </p>
  );
}

// XXX this used to be React.memo() wrapped
const ShowAutocompleteSuggestions = ({
  q,
  highlight,
  suggestions,
  searchSuggestions,
  onSelectSuggestion,
  onSelectSuggestionAll
}) => {
  return (
    <div className="autocomplete">
      <ul>
        {searchSuggestions ? (
          <li
            onClick={onSelectSuggestionAll}
            className={
              highlight === 0 ? "active search-suggestion" : "search-suggestion"
            }
          >
            <p>
              {searchSuggestions.capped ? (
                <a
                  className="total"
                  href={"/q/" + encodeURIComponent(searchSuggestions.term)}
                >
                  {searchSuggestions.total.toLocaleString()}{" "}
                  {searchSuggestions.desperate
                    ? "approximate matches"
                    : "good matches"}
                </a>
              ) : null}
              <a href={"/q/" + encodeURIComponent(searchSuggestions.term)}>
                Search for <b>{q}</b>
              </a>
            </p>
          </li>
        ) : null}

        {suggestions.map((s, index) => {
          let className = index + 1 === highlight ? "active" : null;
          return (
            <li
              key={s.id || s.text}
              className={className}
              onClick={e => onSelectSuggestion(e, s)}
            >
              {s.id ? (
                <ShowAutocompleteSuggestionSong song={s} />
              ) : (
                <p
                  className="simple-autocomplete"
                  dangerouslySetInnerHTML={{ __html: s.html }}
                />
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
};

// XXX this used to be React.memo() wrapped
const ShowAutocompleteSuggestionSong = ({ song }) => {
  let imageUrl = placeholderImage;
  if (song.image) {
    if (song.image.thumbnail100) {
      imageUrl = absolutifyUrl(song.image.thumbnail100);
    } else if (song.image.url) {
      imageUrl = absolutifyUrl(song.image.url);
    }
  }
  return (
    <div className="media autocomplete-suggestion-song">
      <div className="media-left">
        <SongImage url={imageUrl} name={song.name} />
      </div>
      <div className="media-body">
        <h5 className="artist-name">
          <b>{song.name}</b>
          <span className="by">{" by "}</span>
          <span>{song.artist.name}</span>
        </h5>
        {song.fragments.map((fragment, i) => {
          return <p key={i} dangerouslySetInnerHTML={{ __html: fragment }} />;
        })}
      </div>
    </div>
  );
};

const loadedOnce = new Set();

new Image().src = lazyloadThumbnailImage;

class SongImage extends Component {
  state = { loaded: false };

  componentDidMount() {
    this.effect();
  }

  effect = () => {
    const src = this.getCurrentSrc();
    const { url } = this.props;

    if (src === lazyloadThumbnailImage) {
      // We need to preload the eventually needed image.
      this.preloadImg = new Image();

      const self = this;
      function cb() {
        if (!self.dismounted) {
          self.setState({ loaded: true }, () => {
            loadedOnce.add(url);
          });
        }
      }
      // This must come before .decode() otherwise Safari will
      // raise an EncodingError.
      this.preloadImg.src = url;
      // https://html.spec.whatwg.org/multipage/embedded-content.html#dom-img-decode
      // https://developer.mozilla.org/en-US/docs/Web/API/HTMLImageElement/decode#Browser_compatibility
      this.preloadImg.decode
        ? this.preloadImg.decode().then(cb, cb)
        : (this.preloadImg.onload = cb);
      // https://developer.mozilla.org/en-US/docs/Web/API/HTMLImageElement/decoding
      // XXX Why 'sync' and not 'async'??
      this.preloadImg.decoding = "sync";
    }
  };

  componentWillUnmount() {
    if (this.preloadImg) {
      // See https://jsfiddle.net/nw34gLgt/ for demo of this technique.
      // Immediately undo the preloading since we might not need this image.
      this.preloadImg.src = "";
    }
    this.dismounted = true;
  }

  getCurrentSrc = () => {
    const { url } = this.props;
    const { loaded } = this.state;
    if (url) {
      // There is hope! The song has an image.
      if (loadedOnce.has(url) || loaded) {
        return url;
      }
      return lazyloadThumbnailImage;
    }
    return placeholderImage;
  };

  render({ name }) {
    return (
      <img
        className="img-rounded"
        src={this.getCurrentSrc()}
        alt={name}
        title={name}
      />
    );
  }
}
