import React from 'react';
import { Button, Message, Container, Loader } from 'semantic-ui-react';
import { Link } from 'react-router-dom';

import { DisplayDate, ShowServerError, BlogitemBreadcrumb } from './Common';
import { BASE_URL } from './Config';

class BlogitemImages extends React.Component {
  state = {
    images: null,
    loading: true,
    serverError: null,
    updated: null
  };

  componentDidMount() {
    document.title = 'Blogitem Images';
    this.fetchAllImages(this.props.accessToken);
  }

  fetchAllImages = async accessToken => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    const oid = this.props.match.params.oid;
    try {
      const response = await fetch(`/api/v0/plog/${oid}/images`, {
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

  //   pickOpenGraphImage = async src => {
  //     if (!this.props.accessToken) {
  //       throw new Error('No accessToken');
  //     }
  //     const oid = this.props.match.params.oid;
  //     const data = { src };
  //     const response = await fetch(`/api/v0/plog/${oid}/open-graph-image`, {
  //       method: 'POST',
  //       headers: {
  //         Accept: 'application/json',
  //         'Content-Type': 'application/json',
  //         Authorization: `Bearer ${this.props.accessToken}`
  //       },
  //       body: JSON.stringify(data)
  //     });
  //     if (response.ok) {
  //       // const data = await response.json();
  //       // console.log(data);
  //       this.setState({ updated: new Date(), serverError: null }, () => {
  //         window.scrollTo(0, 0);
  //       });
  //     } else {
  //       this.setState({ serverError: response, updated: null }, () => {
  //         window.scrollTo(0, 0);
  //       });
  //     }
  //   };

  //   renderUpdated = () => {
  //     const { updated } = this.state;
  //     if (!updated) return null;

  //     return (
  //       <Message
  //         positive
  //         onDismiss={() => {
  //           this.setState({ updated: null });
  //         }}
  //       >
  //         <Message.Header>Updated</Message.Header>
  //         <p>
  //           <b>
  //             <DisplayDate date={updated} />
  //           </b>
  //         </p>
  //       </Message>
  //     );
  //   };

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
        <BlogitemBreadcrumb oid={oid} page="images" />
        <UploadForm oid={oid} />
      </Container>
    );
  }
}

export default BlogitemImages;

class UploadForm extends React.PureComponent {
  render() {
    return (
      <form>
        <h1>HI</h1>
      </form>
    );
  }
}
