import React, { Component } from 'react';
import { Link } from 'react-router-dom';
import ky from 'ky';
// import logo from './kcco.png';

const fetchCache = {};

class Card extends Component {
  state = {
    card: null,
    loading: true,
    notfound: false
  };

  async componentDidMount() {
    window.scrollTo(0, 0);

    const hash = this.props.match.params[0];
    if (fetchCache[hash]) {
      this.setState({ loading: false, card: fetchCache[hash] });
    } else {
      const paramsString = this.props.location.search.slice(1);
      const searchParams = new URLSearchParams(paramsString);
      const url = searchParams.get('url');
      const response = await ky(`/api/cards/${hash}/?url=${url}`);
      if (response.status === 404) {
        this.setState({ notfound: true });
      } else {
        const data = await response.json();
        this.setState({ loading: false, card: data });
        fetchCache[hash] = data;
      }
    }
  }

  render() {
    const hash = this.props.match.params[0];
    return (
      <div
        className={this.state.loading ? 'is-loading container' : 'container'}
      >
        <SimpleNav current={hash} />
        {this.state.notfound && <h1>Page Not Found</h1>}
        {this.state.card && <ShowCard card={this.state.card} />}
        {this.state.card && <SimpleNav current={hash} />}
      </div>
    );
  }
}

export default Card;

class SimpleNav extends React.PureComponent {
  render() {
    // const { current } = this.props;
    return (
      <nav className="level is-mobile">
        {/* {current && (
          <p className="level-item has-text-centered">
            <Link to={`/${current}/previous`} className="link is-info">
              Previous
            </Link>
          </p>
        )} */}
        <p className="level-item has-text-centered">
          <Link to="/" className="button is-info">
            {/* <img src={logo} />  */}
            Home
          </Link>
        </p>
        {/* {current && (
          <p className="level-item has-text-centered">
            <Link to={`/${current}/next`} className="link is-info">
              Next
            </Link>
          </p>
        )} */}
      </nav>
    );
  }
}
class ShowCard extends React.PureComponent {
  componentWillMount() {
    document.title = this.props.card.text;
  }
  render() {
    const { card } = this.props;
    return (
      <div className="content">
        <h2>{card.text}</h2>
        <div className="pictures">
          {card.pictures.map(picture => {
            return (
              <div className="box" key={picture.img}>
                <article className="media">
                  <div className="media-content">
                    <div className="content">
                      <Image
                        src={picture.img}
                        gifsrc={picture.gifsrc}
                        caption={card.caption}
                      />

                      {card.caption && <p>{card.caption}</p>}
                    </div>
                  </div>
                </article>
              </div>
            );
          })}
        </div>
      </div>
    );
  }
}

class Image extends React.PureComponent {
  async componentDidMount() {
    const { gifsrc } = this.props;
    console.log('COULD PRELOAD', gifsrc);
  }
  render() {
    const { src, gifsrc, caption } = this.props;
    // if (gifsrc) {
    //   return (
    //     <img src={src} className="is-overlay" alt={caption || 'no caption'} />
    //   );
    // } else {
    //   return <img src={src} alt={caption || 'no caption'} />;
    // }
    return <img src={gifsrc || src} alt={caption || 'no caption'} />;
  }
}
