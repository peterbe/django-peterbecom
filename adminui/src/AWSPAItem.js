import React from 'react';
import {
  Button,
  Container,
  Header,
  List,
  Loader,
  Message,
  Table
} from 'semantic-ui-react';
import { Link } from 'react-router-dom';
import { DisplayDate, ShowServerError } from './Common';

class AWSPAItem extends React.Component {
  state = {
    loading: true,
    data: null,
    serverError: null
  };

  componentDidMount() {
    document.title = 'AWSPA Item';
    this.fetchItem();
  }

  componentDidUpdate(prevProps) {
    if (prevProps.match.params.id !== this.props.match.params.id) {
      this.fetchItem();
    }
  }

  fetchItem = () => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    this.setState({ loading: true }, async () => {
      const id = this.props.match.params.id;
      let response;
      try {
        response = await fetch(`/api/v0/awspa/${id}`, {
          headers: {
            Authorization: `Bearer ${this.props.accessToken}`
          }
        });
      } catch (ex) {
        return this.setState({ loading: false, serverError: ex });
      }
      this.setState({ loading: false });
      if (response.ok) {
        const data = await response.json();
        document.title = `AWSPA Item (${data.asin})`;
        this.setState({ data, serverError: null });
      } else {
        this.setState({ serverError: response });
      }
    });
  };

  toggleDisable = () => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    this.setState({ loading: true }, async () => {
      const id = this.props.match.params.id;
      let response;
      const formData = new FormData();
      formData.append('disable', true);
      try {
        response = await fetch(`/api/v0/awspa/${id}`, {
          method: 'POST',
          body: formData,
          headers: {
            Authorization: `Bearer ${this.props.accessToken}`
          }
        });
      } catch (ex) {
        return this.setState({ loading: false, serverError: ex });
      }
      this.setState({ loading: false });
      if (response.ok) {
        const data = await response.json();
        this.setState({ data, serverError: null });
      } else {
        this.setState({ serverError: response });
      }
    });
  };

  refreshProduct = () => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    this.setState({ loading: true }, async () => {
      const id = this.props.match.params.id;
      let response;
      const formData = new FormData();
      formData.append('refresh', true);
      try {
        response = await fetch(`/api/v0/awspa/${id}`, {
          method: 'POST',
          body: formData,
          headers: {
            Authorization: `Bearer ${this.props.accessToken}`
          }
        });
      } catch (ex) {
        return this.setState({ loading: false, serverError: ex });
      }
      this.setState({ loading: false });
      if (response.ok) {
        const data = await response.json();
        this.setState({ data, serverError: null });
      } else {
        this.setState({ serverError: response });
      }
    });
  };

  deleteProduct = () => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    this.setState({ loading: true }, async () => {
      const id = this.props.match.params.id;
      let response;
      try {
        response = await fetch(`/api/v0/awspa/${id}`, {
          method: 'DELETE',
          headers: {
            Authorization: `Bearer ${this.props.accessToken}`
          }
        });
      } catch (ex) {
        return this.setState({ loading: false, serverError: ex });
      }
      this.setState({ loading: false });
      if (response.ok) {
        this.setState({ serverError: null }, () => {
          window.location.href = '/awspa';
        });
      } else {
        this.setState({ serverError: response });
      }
    });
  };

  render() {
    const { loading, data, serverError } = this.state;

    if (!serverError && loading) {
      return (
        <Container>
          <Loader
            active
            content="Loading AWSPA Item..."
            inline="centered"
            size="massive"
            style={{ margin: '200px 0' }}
          />
        </Container>
      );
    }
    return (
      <Container>
        <ShowServerError error={this.state.serverError} />
        <GoBackLink search={this.props.location.search} />
        <Header as="h1">AWSPA Item {data && <code>{data.asin}</code>}</Header>
        {data && (
          <div className="all-keywords">
            <ShowItem
              toggleDisable={this.toggleDisable}
              refreshProduct={this.refreshProduct}
              deleteProduct={this.deleteProduct}
              data={data}
              loading={loading}
            />
          </div>
        )}
      </Container>
    );
  }
}

export default AWSPAItem;

function GoBackLink({ search }) {
  let oid = null;
  if (search) {
    const params = new URLSearchParams(search.slice(1));
    oid = params.get('oid');
  }
  if (!oid) {
    return (
      <Message>
        <Link to={`/awspa`}>All AWS Affiliate Product items</Link>
      </Message>
    );
  }
  return (
    <Message positive>
      <Link to={`/plog/${oid}/awspa`}>Go back to blog post's AWSPA</Link>
    </Message>
  );
}

function ShowItem({
  toggleDisable,
  refreshProduct,
  deleteProduct,
  loading,
  data
}) {
  return (
    <div>
      {data.disabled && (
        <Message negative>
          <Message.Header>Disabled!</Message.Header>
          <p>Won't show up in blog posts.</p>
        </Message>
      )}
      <Header as="h2">Metadata</Header>
      <Table definition>
        <Table.Body>
          <Table.Row>
            <Table.Cell>Title</Table.Cell>
            <Table.Cell>
              <a
                href={data.payload.detail_page_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {data.title}
              </a>
            </Table.Cell>
          </Table.Row>
          <Table.Row>
            <Table.Cell>Keyword</Table.Cell>
            <Table.Cell>{data.keyword}</Table.Cell>
          </Table.Row>
          <Table.Row>
            <Table.Cell>Searchindex</Table.Cell>
            <Table.Cell>{data.searchindex}</Table.Cell>
          </Table.Row>
          <Table.Row>
            <Table.Cell>Added</Table.Cell>
            <Table.Cell>
              <DisplayDate date={data.add_date} />
            </Table.Cell>
          </Table.Row>
          <Table.Row>
            <Table.Cell>Modified</Table.Cell>
            <Table.Cell>
              <DisplayDate date={data.modify_date} />
            </Table.Cell>
          </Table.Row>
          <Table.Row>
            <Table.Cell>PAAPIv5</Table.Cell>
            <Table.Cell>
              {data.paapiv5 ? (
                <span aria-label="check" role="img">
                  ✅
                </span>
              ) : (
                <span aria-label="no" role="img">
                  ❌
                </span>
              )}
            </Table.Cell>
          </Table.Row>
        </Table.Body>
      </Table>
      <Header as="h2">Actions</Header>
      <Button disabled={loading} onClick={toggleDisable}>
        {data.disabled ? 'Enable' : 'Disable'}
      </Button>
      <Button disabled={loading} onClick={deleteProduct}>
        Delete
      </Button>
      <Button disabled={loading} onClick={refreshProduct}>
        Refresh
      </Button>

      <Header as="h2">Preview</Header>
      <div className="ui divided items">
        {data.html ? (
          <div
            className="item"
            dangerouslySetInnerHTML={{ __html: data.html }}
          />
        ) : (
          <div>
            <Header as="h4" style={{ color: 'red' }}>
              Preview Error!
            </Header>
            <pre>{data.html_error}</pre>
          </div>
        )}
      </div>

      {data.same_asin && data.same_asin.length ? (
        <div>
          <Header as="h2">
            Same ASIN, Different products ({data.same_asin.length})
          </Header>
          <List>
            {data.same_asin.map(p => {
              return (
                <List.Item key={p.id}>
                  <List.Content>
                    <List.Header>
                      <Link to={`/awspa/${p.id}`}>{p.title}</Link>{' '}
                      {p.disabled && <b>Disabled!</b>}
                    </List.Header>
                    <List.Description>
                      <b>Added:</b> <DisplayDate date={p.add_date} />{' '}
                      <b>Modified:</b> <DisplayDate date={p.modify_date} />{' '}
                      <b>PAAPIv5:</b>{' '}
                      {p.paapiv5 ? (
                        <span aria-label="check" role="img">
                          ✅
                        </span>
                      ) : (
                        <span aria-label="no" role="img">
                          ❌
                        </span>
                      )}{' '}
                    </List.Description>
                  </List.Content>
                </List.Item>
              );
            })}
          </List>
        </div>
      ) : null}

      <Header as="h2">Payload</Header>
      <pre>{JSON.stringify(data.payload, null, 3)}</pre>
    </div>
  );
}
