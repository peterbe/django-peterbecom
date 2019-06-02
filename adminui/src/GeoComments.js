import React from 'react';
import { Container, Header, Loader, Dimmer, Segment } from 'semantic-ui-react';
import {
  withScriptjs,
  withGoogleMap,
  GoogleMap,
  Marker
} from 'react-google-maps';

import { ShowServerError } from './Common';

class GeoComments extends React.Component {
  state = {
    loading: false,
    comments: null,
    apiKey: null,
    serverError: null
  };
  componentDidMount() {
    document.title = 'Geo Comments';
    this.setState({ loading: true }, this.loadComments);
  }

  loadComments = async () => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    let response;
    let url = '/api/v0/plog/comments/geo/';
    try {
      response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${this.props.accessToken}`
        }
      });
    } catch (ex) {
      return this.setState({ loading: false, serverError: ex });
    }

    if (this.dismounted) {
      return;
    }
    if (response.ok) {
      const result = await response.json();
      this.setState({
        loading: false,
        comments: result.comments,
        apiKey: result.google_maps_api_key,
        serverError: null
      });
    } else {
      this.setState({ loading: false, serverError: response });
    }
  };
  componentWillUnmount() {
    this.dismounted = true;
  }

  render() {
    const { apiKey, serverError, loading, comments } = this.state;
    return (
      <Container textAlign="center">
        <Header as="h1">Geo Comments</Header>
        <ShowServerError error={serverError} />
        <Segment basic>
          <Dimmer active={loading} inverted>
            <Loader inverted>Loading</Loader>
          </Dimmer>
          {comments && apiKey && (
            <ShowMap comments={comments} apiKey={apiKey} />
          )}
        </Segment>
      </Container>
    );
  }
}

export default GeoComments;

const MyMapComponent = withScriptjs(
  withGoogleMap(props => (
    <GoogleMap defaultZoom={1} defaultCenter={{ lat: -34.397, lng: 150.644 }}>
      {props.markers.map(marker => (
        <Marker key={marker.id} position={marker.position} />
      ))}
      {/* {props.isMarkerShown && (
        <Marker position={{ lat: -34.397, lng: 150.644 }} />
      )} */}
    </GoogleMap>
  ))
);

function ShowMap({ comments, apiKey }) {
  const markers = comments.map(comment => {
    return {
      id: comment.id,
      position: {
        lat: comment.location.latitude,
        lng: comment.location.longitude
      },
      title: comment.blogitem.title
    };
  });
  return (
    <MyMapComponent
      isMarkerShown
      googleMapURL={`https://maps.googleapis.com/maps/api/js?key=${apiKey}&v=3.exp&libraries=geometry,drawing,places`}
      loadingElement={<div style={{ height: `100%` }} />}
      containerElement={<div style={{ height: `400px` }} />}
      mapElement={<div style={{ height: `100%` }} />}
      markers={markers}
    />
  );
}
