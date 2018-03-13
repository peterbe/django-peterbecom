import React from 'react';
import './App.css';
import { throttle, debounce } from 'throttle-debounce';
import placeholderImage from './placeholder.png';

const SERVER = process.env.REACT_APP_SERVER_URL || 'https://songsear.ch';

const appendSuggestion = (text, append) => {
  let split = text.split(/\s+/);
  split.pop();
  split.push(append);
  return split.join(' ');
};

const absolutifyUrl = uri => {
  if (uri.charAt(0) === '/' && uri.charAt(1) !== '/') {
    return SERVER + uri;
  }
  return uri;
};

const convertLazyLoadImages = (once = false) => {
  const inner = () => {
    const nodelist = document.querySelectorAll('img[data-src]');
    let count = 0;
    [...nodelist].forEach(img => {
      const trueSrc = img.dataset.src;
      delete img.dataset.src;
      img.src = trueSrc;
      if (img.classList) {
        img.classList.remove('lazyload');
        img.classList.remove('preview');
      }
      count++;
    });
    return count;
  };
  const wrap = debounce(200, true, inner);

  if (once) {
    wrap();
  } else {
    setTimeout(wrap, 40);
    setTimeout(wrap, 300);
  }
};

class App extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      q: '',
      autocompleteSuggestions: null,
      autocompleteHighlight: -1,
      showAutocompleteSuggestions: true,
    };

    this.fetchAutocompleteSuggestionsDebounced = debounce(
      500,
      this.fetchAutocompleteSuggestions
    );
    this.fetchAutocompleteSuggestionsThrottled = throttle(
      700,
      this.fetchAutocompleteSuggestions
    );

    this._fetchAutocompleteSuggestionsCache = {};
  }

  componentDidMount() {
    // If the <input> HTML had something typed into it when the React
    // app started, that would be passed to the App when initialized.
    // For example if the React app is slow to load. I.e. async slow.
    if (this.props.initialValue && !this.state.q) {
      this.setState({ q: this.props.initialValue });
    }
  }

  submitSearch = event => {
    event.preventDefault();
    this._submit(this.state.q);
  };

  _submit = (q, submitevent = 'enter') => {
    q = q.trim();
    if (!q) {
      return;
    }
    let gotoURL = `${SERVER}/q/${q}?autocomplete=${submitevent}`;
    document.location.href = gotoURL;
    if (this.state.autocompleteSuggestions) {
      this.setState({
        autocompleteSuggestions: null,
        autocompleteHighlight: -1,
        showAutocompleteSuggestions: true,
      });
    }
  };

  onFocusSearch = event => {
    if (!this.state.showAutocompleteSuggestions) {
      this.setState({ showAutocompleteSuggestions: true });
    }
  };

  onBlurSearch = event => {
    setTimeout(() => {
      this.setState({
        showAutocompleteSuggestions: false,
      });
    }, 300);
  };

  onChangeSearch = event => {
    const qUntrimmed = event.target.value;
    const q = qUntrimmed.trim();
    this.setState({ q: qUntrimmed }, () => {
      const length = q.length;
      if (length < 6 || qUntrimmed.endsWith(' ')) {
        // The impatient one.
        this.fetchAutocompleteSuggestionsThrottled(q);
      } else if (length) {
        // The patient one.
        this.fetchAutocompleteSuggestionsDebounced(q);
      } else {
        this.setState({
          autocompleteSuggestions: null,
          autocompleteSearchSuggestions: null,
          autocompleteHighlight: -1,
          showAutocompleteSuggestions: true,
        });
      }
    });
  };

  fetchAutocompleteSuggestions = q => {
    let url = `${SERVER}/api/search/autocomplete?q=${q}`;
    const cached = this._fetchAutocompleteSuggestionsCache[q];
    if (cached) {
      return Promise.resolve(cached).then(results => {
        this.setState({
          autocompleteSuggestions: results.matches,
          autocompleteSearchSuggestions: results.search_suggestions,
          autocompleteHighlight: -1,
        });
      });
    }
    this.waitingFor = q;
    fetch(url).then(r => {
      if (r.status === 200) {
        if (q.startsWith(this.waitingFor)) {
          r.json().then(results => {
            this._fetchAutocompleteSuggestionsCache[q] = results;
            this.setState({
              autocompleteSuggestions: results.matches,
              autocompleteSearchSuggestions: results.search_suggestions,
              autocompleteHighlight: -1,
            });
          });
        }
      }
    });
  };

  onKeyDownSearch = event => {
    let suggestions = this.state.autocompleteSuggestions;
    if (suggestions) {
      let highlight = this.state.autocompleteHighlight;
      if (event.key === 'Tab') {
        event.preventDefault();
        let suggestion =
          highlight > -1 ? suggestions[highlight] : suggestions[0];
        if (suggestion.append) {
          this.setState({
            q: appendSuggestion(this.state.q, suggestion.text) + ' ',
            autocompleteSuggestions: null,
            autocompleteHighlight: -1,
          });
        } else {
          this.setState({
            q: suggestion.text + ' ',
          });
          this.fetchAutocompleteSuggestions(suggestion.text);
        }
      } else if (event.key === 'ArrowDown' && highlight < suggestions.length) {
        event.preventDefault();
        this.setState({ autocompleteHighlight: highlight + 1 });
      } else if (event.key === 'ArrowUp' && highlight > -1) {
        this.setState({ autocompleteHighlight: highlight - 1 });
      } else if (event.key === 'Enter') {
        if (highlight > -1) {
          event.preventDefault();
          const searchSuggestions = this.state.autocompleteSearchSuggestions;
          if (highlight === 0 && searchSuggestions && searchSuggestions.total) {
            this._submit(this.state.q, 'search');
            return;
          }
          highlight--;
          if (suggestions[highlight]._url) {
            this.setState({
              // XXX perhaps there should be something that updates
              // the state to say we're redirecting.
              autocompleteSuggestions: null,
              autocompleteHighlight: -1,
            });
            document.location.href = absolutifyUrl(suggestions[highlight]._url);
            return;
          } else {
            this.setState(
              {
                q: suggestions[highlight].text,
                autocompleteSuggestions: null,
                autocompleteHighlight: -1,
              },
              () => this._submit(this.state.q)
            );
          }
        }
      }
    }
  };

  onSelectSuggestion = (event, suggestion) => {
    event.preventDefault();
    if (suggestion._url) {
      this.setState({
        // XXX perhaps there should be something that updates
        // the state to say we're redirecting.
        autocompleteSuggestions: null,
        autocompleteHighlight: -1,
      });
      document.location.href = absolutifyUrl(suggestion._url);
      return;
    }
    let newText = suggestion.text;
    if (suggestion.append) {
      newText = appendSuggestion(this.state.q, newText);
    }
    this.setState(
      {
        q: newText,
        autocompleteSuggestions: null,
        autocompleteHighlight: -1,
      },
      () => {
        this._submit(suggestion.text, 'clicked');
      }
    );
  };

  onSelectSuggestionAll = event => {
    event.preventDefault();
    this._submit(this.state.q, 'search');
  };

  render() {
    return (
      <form
        style={{ margin: '50px 0' }}
        action={`${SERVER}/q/`}
        onSubmit={this.submitSearch}
      >
        <div
          className="ui big icon input fluid"
          style={{ display: 'relative' }}
        >
          <input
            type="search"
            name="term"
            value={this.state.q}
            onFocus={this.onFocusSearch}
            onBlur={this.onBlurSearch}
            onChange={this.onChangeSearch}
            onKeyDown={this.onKeyDownSearch}
            className="form-control x-large"
            placeholder="Type your search here..."
          />
          <i className="search icon" />
          {this.state.autocompleteSuggestions &&
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
      </form>
    );
  }
}

export default App;

class ShowAutocompleteSuggestions extends React.PureComponent {
  componentDidMount() {
    this._maybeConvertLazyLoadImages(this.props.suggestions);
  }

  componentWillReceiveProps(nextProps) {
    this._maybeConvertLazyLoadImages(nextProps.suggestions);
  }

  _maybeConvertLazyLoadImages = suggestions => {
    if (suggestions.some(suggestion => !!suggestion.id)) {
      convertLazyLoadImages();
    }
  };

  render() {
    const {
      q,
      highlight,
      suggestions,
      searchSuggestions,
      onSelectSuggestion,
      onSelectSuggestionAll,
    } = this.props;
    if (!suggestions.length) {
      return null;
    }
    return (
      <div className="autocomplete">
        <ul>
          {searchSuggestions &&
          searchSuggestions.total &&
          searchSuggestions.capped ? (
            <li
              onClick={onSelectSuggestionAll}
              className={
                highlight === 0
                  ? 'active search-suggestion'
                  : 'search-suggestion'
              }
            >
              {searchSuggestions.capped ? (
                <a
                  style={{ float: 'right' }}
                  href={'/q/' + encodeURIComponent(searchSuggestions.term)}
                >
                  {numberWithCommas(searchSuggestions.total)}{' '}
                  {searchSuggestions.desperate
                    ? 'approximate matches'
                    : 'good matches'}
                </a>
              ) : null}
              <a href={'/q/' + encodeURIComponent(searchSuggestions.term)}>
                Search for <i>{q}</i>
              </a>
            </li>
          ) : null}

          {suggestions.map((s, index) => {
            let className = index + 1 === highlight ? 'active' : '';
            return (
              <li
                key={index}
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
  }
}

class ShowAutocompleteSuggestionSong extends React.PureComponent {
  render() {
    const { song } = this.props;
    return (
      <div className="media autocomplete-suggestion-song">
        <div className="media-left">
          <img
            className={
              song.image && song.image.preview
                ? 'img-rounded lazyload preview'
                : 'img-rounded lazyload'
            }
            src={
              song.image && song.image.preview
                ? song.image.preview
                : placeholderImage
            }
            data-src={
              song.image ? absolutifyUrl(song.image.url) : placeholderImage
            }
            alt={song.name}
          />
        </div>
        <div className="media-body">
          <h5 className="artist-name">
            <b>{song.name}</b>
            {' by '}
            <span>{song.artist.name}</span>
          </h5>
          {song.fragments.map((fragment, i) => {
            return <p key={i} dangerouslySetInnerHTML={{ __html: fragment }} />;
          })}
        </div>
      </div>
    );
  }
}

/* http://stackoverflow.com/a/2901298 */
const numberWithCommas = function(x) {
  var parts = x.toString().split('.');
  parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return parts.join('.');
};
