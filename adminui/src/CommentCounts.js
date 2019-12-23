import React from 'react';
import { Container, Header } from 'semantic-ui-react';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';

import '@fullcalendar/core/main.min.css';
import '@fullcalendar/daygrid/main.min.css';
import '@fullcalendar/timegrid/main.min.css';

import { ShowServerError } from './Common';

class CommentCounts extends React.Component {
  state = {
    loading: false,
    comments: null,
    serverError: null
  };
  componentDidMount() {
    document.title = 'Comment Counts';
  }

  componentWillUnmount() {
    this.dismounted = true;
  }

  getEvents = (fetchInfo, successCallback, failureCallback) => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    this.setState({ loading: true }, async () => {
      let url = '/api/v0/plog/comments/counts/';
      const searchParams = new URLSearchParams();
      Object.entries(fetchInfo).forEach(([key, value]) => {
        if (Array.isArray(value) && value.length) {
          value.forEach(v => searchParams.append(key, v));
        } else if (value && value.toISOString) {
          searchParams.set(key, value.toISOString());
        } else if (value) {
          searchParams.set(key, value);
        }
      });
      url += `?${searchParams.toString()}`;
      let response;
      try {
        response = await fetch(url, {
          headers: {
            Authorization: `Bearer ${this.props.accessToken}`
          }
        });
        if (response.ok) {
          const result = await response.json();
          successCallback(result.events);
        } else {
          const err = new Error(response.statusText);
          failureCallback(err);
        }
      } catch (ex) {
        failureCallback(ex);
      }
      this.setState({ loading: false });
    });
  };

  render() {
    const { serverError, loading } = this.state;
    return (
      <Container textAlign="center">
        <Header as="h1">Comment Counts</Header>
        <ShowServerError error={serverError} />
        <FullCalendar
          defaultView="dayGridMonth"
          plugins={[dayGridPlugin, timeGridPlugin]}
          events={this.getEvents}
          header={{
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek'
          }}
        />
        <small>{loading ? 'loading...' : ''}</small>
      </Container>
    );
  }
}

export default CommentCounts;
