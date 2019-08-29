import React from 'react';
import {
  Table,
  Container,
  Header,
  Flag,
  Loader,
  Dimmer,
  Segment
} from 'semantic-ui-react';
import {
  withScriptjs,
  withGoogleMap,
  GoogleMap,
  Marker
} from 'react-google-maps';

import { ShowServerError } from './Common';
import { BASE_URL } from './Config';

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
            <ShowComments comments={comments} apiKey={apiKey} />
          )}
        </Segment>
      </Container>
    );
  }
}

export default GeoComments;

const MyMapComponent = withScriptjs(
  withGoogleMap(props => (
    <GoogleMap
      defaultZoom={2}
      defaultCenter={{ lat: 42.189451, lng: -5.01385 }}
    >
      {props.markers.map(marker => (
        <Marker key={marker.id} position={marker.position} />
      ))}
      {/* {props.isMarkerShown && (
        <Marker position={{ lat: -34.397, lng: 150.644 }} />
      )} */}
    </GoogleMap>
  ))
);

function ShowComments({ comments, apiKey }) {
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
    <div>
      <MyMapComponent
        isMarkerShown
        googleMapURL={`https://maps.googleapis.com/maps/api/js?key=${apiKey}&v=3.exp&libraries=geometry,drawing,places`}
        loadingElement={<div style={{ height: `100%` }} />}
        containerElement={<div style={{ height: `600px` }} />}
        mapElement={<div style={{ height: `100%` }} />}
        markers={markers}
      />

      <Table>
        <Table.Header>
          <Table.Row>
            <Table.HeaderCell>Comment</Table.HeaderCell>
            <Table.HeaderCell>City</Table.HeaderCell>
            <Table.HeaderCell>Country</Table.HeaderCell>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {comments.map(comment => {
            return (
              <Table.Row key={comment.id}>
                <Table.Cell>
                  {comment.name || <i>no name</i>}
                  <span> on </span>
                  <a href={BASE_URL + `/plog/${comment.blogitem.oid}`}>
                    {comment.blogitem.title}
                  </a>
                </Table.Cell>
                <Table.Cell>
                  {comment.location.city || <i>no city</i>}
                </Table.Cell>
                <Table.Cell>
                  {comment.location.country_name && (
                    <Flag
                      name={comment.location.country_code.toLowerCase()}
                      title={comment.location.country_name}
                    />
                  )}{' '}
                  {comment.location.country_name || <i>no country</i>}
                </Table.Cell>
              </Table.Row>
            );
          })}
        </Table.Body>
      </Table>
    </div>
  );
}
