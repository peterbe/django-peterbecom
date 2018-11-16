import React from 'react';
import { Button, Message, Container, Loader } from 'semantic-ui-react';
import { Link } from 'react-router-dom';

import { DisplayDate, ShowServerError, BlogitemBreadcrumb } from './Common';
import { BASE_URL } from './Config';

class OpenGraphImageBlogitem extends React.Component {
  state = {
    images: null,
    loading: true,
    serverError: null,
    updated: null
  };

  componentDidMount() {
    document.title = 'Open Graph Image';
    this.fetchAllImages(this.props.accessToken);
  }

  fetchAllImages = async accessToken => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    const oid = this.props.match.params.oid;
    try {
      const response = await fetch(`/api/v0/plog/${oid}/open-graph-image`, {
        headers: {
          Authorization: `Bearer ${this.props.accessToken}`
        }
      });
      this.setState({ loading: false });
      if (response.ok) {
        const json = await response.json();
        this.setState({ images: json.images });
      } else {
        this.setState({ serverError: response }, () => {
          window.scrollTo(0, 0);
        });
      }
    } catch (ex) {
      this.setState({ serverError: ex }, () => {
        window.scrollTo(0, 0);
      });
    }
  };

  pickOpenGraphImage = async src => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    const oid = this.props.match.params.oid;
    const data = { src };
    const response = await fetch(`/api/v0/plog/${oid}/open-graph-image`, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        Authorization: `Bearer ${this.props.accessToken}`
      },
      body: JSON.stringify(data)
    });
    if (response.ok) {
      // const data = await response.json();
      // console.log(data);
      this.setState({ updated: new Date(), serverError: null }, () => {
        window.scrollTo(0, 0);
      });
    } else {
      this.setState({ serverError: response, updated: null }, () => {
        window.scrollTo(0, 0);
      });
    }
  };

  renderUpdated = () => {
    const { updated } = this.state;
    if (!updated) return null;

    return (
      <Message
        positive
        onDismiss={() => {
          this.setState({ updated: null });
        }}
      >
        <Message.Header>Updated</Message.Header>
        <p>
          <b>
            <DisplayDate date={updated} />
          </b>
        </p>
      </Message>
    );
  };

  render() {
    const { loading, serverError, images } = this.state;
    const oid = this.props.match.params.oid;
    if (!serverError && loading) {
      return (
        <Container>
          <Loader
            active
            size="massive"
            inline="centered"
            content="Loading Images..."
            style={{ margin: '200px 0' }}
          />
        </Container>
      );
    }
    return (
      <Container>
        <BlogitemBreadcrumb oid={oid} page="open_graph_image" />
        <ShowServerError error={this.state.serverError} />
        {this.renderUpdated()}
        {images && (
          <Images
            oid={oid}
            images={images}
            onPicked={image => {
              this.pickOpenGraphImage(image.src);
            }}
            onRemove={image => {
              throw new Error('Work harder');
            }}
          />
        )}
      </Container>
    );
  }
}

export default OpenGraphImageBlogitem;

class Images extends React.PureComponent {
  render() {
    const { oid, images } = this.props;
    return (
      <div>
        <h2>{images.length} images found</h2>
        <h5>
          <Link to={`/plog/${oid}`}>Back to Edit</Link>
        </h5>
        {images.map(image => {
          // console.log('IMAGE', image);
          return (
            <div
              key={image.src}
              style={{
                borderBottom: '1px solid #666',
                marginBottom: 50,
                paddingBottom: 20
              }}
            >
              <img src={BASE_URL + image.src} alt={image.title} />
              <p>
                <b>{image.label}</b>
                <br />
                <i>
                  {image.size[0]}x{image.size[1]}
                </i>
                <br />
                {image.used_in_text && <b>Found in text!</b>}
              </p>
              <Button
                disabled={image.current}
                onClick={event => {
                  event.preventDefault();
                  this.props.onPicked(image);
                }}
              >
                This one!
              </Button>
            </div>
          );
        })}
      </div>
    );
  }
}
