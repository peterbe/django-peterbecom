import React from 'react';
import md5 from 'md5';
import {
  Button,
  Segment,
  Checkbox,
  Container,
  Loader,
  Comment,
  Flag,
  List,
  Header,
  Icon,
  Select,
  Input,
  Message,
  TextArea,
  Form
} from 'semantic-ui-react';
import { parseISO, formatDistance } from 'date-fns/esm';
import { DisplayDate, ShowServerError } from './Common';
import { BASE_URL } from './Config';

function getDefault(props, key, defaultValue) {
  const { location } = props;
  if (location.search) {
    const searchParams = new URLSearchParams(
      location.search.slice(1, location.search.length)
    );
    if (key === 'approved') {
      return searchParams.get('approved') === 'not';
    } else {
      return searchParams.get(key) || '';
    }
  }
  return defaultValue;
}

class Comments extends React.Component {
  state = {
    comments: null,
    count: 0,
    oldest: null,
    serverError: null,
    loading: false,
    search: getDefault(this.props, 'search', ''),
    unapprovedOnly: getDefault(this.props, 'unapproved', '') === 'only',
    autoapprovedOnly: getDefault(this.props, 'autoapproved', '') === 'only',
    checkedForApproval: {},
    checkedForDelete: {},
    editing: {},
    approved: {},
    deleted: {},
    deleting: {},
    approving: {}
  };

  componentDidMount() {
    document.title = 'Comments';
    this.fetchComments();
  }

  componentDidUpdate(prevProps, prevState) {
    if (prevState.count !== this.state.count) {
      document.title = `(${this.state.count.toLocaleString()}) Comments`;
    }
    if (this.props.location.search !== prevProps.location.search) {
      this.setState(
        {
          unapprovedOnly: getDefault(this.props, 'unapproved', '') === 'only',
          autoapprovedOnly:
            getDefault(this.props, 'autoapproved', '') === 'only'
        },
        () => {
          this.fetchComments();
        }
      );
    }
  }

  fetchComments = (loadMore = false) => {
    this.setState({ loading: true }, async () => {
      const { accessToken } = this.props;
      if (!accessToken) {
        throw new Error('No accessToken');
      }
      const { oldest, search } = this.state;
      let url = `/api/v0/plog/comments/?search=${encodeURIComponent(search)}`;
      if (loadMore) {
        url += `&since=${encodeURIComponent(oldest)}`;
      }
      if (this.state.unapprovedOnly) {
        url += '&unapproved=only';
      } else if (this.state.autoapprovedOnly) {
        url += '&autoapproved=only';
      }
      let response;
      try {
        response = await fetch(url, {
          headers: {
            Authorization: `Bearer ${accessToken}`
          }
        });
      } catch (ex) {
        return this.setState({ loading: false, serverError: ex });
      }

      if (response.ok) {
        const data = await response.json();
        this.setState({
          comments: data.comments,
          count: data.count,
          oldest: data.oldest,
          countries: data.countries,
          loading: false
        });
      } else {
        this.setState({ serverError: response, loading: false });
      }
    });
  };

  deleteComments = async oids => {
    const deleting = {};
    oids.forEach(oid => {
      deleting[oid] = true;
    });
    this.setState({ loading: true, deleting }, async () => {
      await this._deleteOrApproveComments('delete', { oids });
      const deleted = Object.assign({}, this.state.deleted);
      oids.forEach(oid => {
        deleted[oid] = true;
      });
      this.setState({ deleting: {}, deleted }, () => {
        this._resetChecked(oids);
      });
    });
  };

  approveComments = async oids => {
    const approving = {};
    oids.forEach(oid => {
      approving[oid] = true;
    });
    this.setState({ loading: true, approving }, async () => {
      await this._deleteOrApproveComments('approve', { oids });
      const approved = Object.assign({}, this.state.approved);
      oids.forEach(oid => {
        approved[oid] = true;
      });
      this.setState({ approving: {}, approved }, () => {
        this._resetChecked(oids);
      });
    });
  };

  _resetChecked = oids => {
    const checkedForApproval = this.state.checkedForApproval;
    const checkedForDelete = this.state.checkedForDelete;
    oids.forEach(oid => {
      delete checkedForApproval[oid];
      delete checkedForDelete[oid];
    });
    this.setState({ checkedForApproval, checkedForDelete });
  };

  _deleteOrApproveComments = async (type, data) => {
    const { accessToken } = this.props;
    if (!accessToken) {
      throw new Error('No accessToken');
    }
    if (!(type === 'delete' || type === 'approve')) {
      throw new Error(`Invalid endpoint ${type}`);
    }
    const url = `/api/v0/plog/comments/${type}/`;
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`
        },
        body: JSON.stringify(data)
      });
      if (response.ok) {
        this.setState({
          loading: false,
          serverError: null
        });
      } else {
        this.setState({ serverError: response, loading: false });
      }
    } catch (ex) {
      this.setState({ serverError: ex, loading: false });
    }
  };

  editComment = async (comment, data) => {
    this.setState({ loading: true });

    const { accessToken } = this.props;
    if (!accessToken) {
      throw new Error('No accessToken');
    }
    // const data = { comment: text, oid: comment.oid };
    // Correct the alias
    data.comment = data.text;
    data.oid = comment.oid;
    const url = `/api/v0/plog/comments/`;
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`
        },
        body: JSON.stringify(data)
      });
      if (response.ok) {
        const data = await response.json();
        function mutateCommentTexts(comments) {
          comments.forEach(c => {
            if (c.oid === comment.oid) {
              c.comment = data.comment;
              c.name = data.name;
              c.email = data.email;
              c.rendered = data.rendered;
              c._clues = data._clues;
            } else {
              mutateCommentTexts(c.replies);
            }
          });
        }
        const comments = this.state.comments;
        mutateCommentTexts(comments);
        const editing = Object.assign({}, this.state.editing);
        editing[comment.oid] = false;
        this.setState({
          comments,
          editing,
          loading: false,
          serverError: null
        });
      } else {
        this.setState({ serverError: response, loading: false });
      }
    } catch (ex) {
      console.error(ex);
      this.setState({ serverError: ex, loading: false });
    }
  };

  render() {
    const {
      loading,
      comments,
      countries,
      serverError,
      unapprovedOnly,
      autoapprovedOnly
    } = this.state;
    return (
      <Container>
        <ShowServerError error={serverError} />
        {comments === null && serverError === null ? (
          <Loader
            active
            size="massive"
            inline="centered"
            content="Loading Comments..."
            style={{ margin: '200px 0' }}
          />
        ) : null}

        {comments && (
          <FilterForm
            search={this.state.search}
            unapprovedOnly={unapprovedOnly}
            autoapprovedOnly={autoapprovedOnly}
            update={updates => {
              console.log('UPDATE:', updates);
              this.setState(updates, () => {
                let newURL = new URL(
                  this.props.location.pathname,
                  document.location.href
                );

                if (this.state.search) {
                  newURL.searchParams.set('search', this.state.search);
                }
                if (this.state.unapprovedOnly) {
                  newURL.searchParams.set('unapproved', 'only');
                } else if (this.state.autoapprovedOnly) {
                  newURL.searchParams.set('autoapproved', 'only');
                }
                this.props.history.push(newURL.pathname + newURL.search);
                this.fetchComments();
              });
            }}
          />
        )}
        {
          <Checked
            checkedForApproval={this.state.checkedForApproval}
            checkedForDelete={this.state.checkedForDelete}
            deleteComments={this.deleteComments}
            approveComments={this.approveComments}
          />
        }

        {comments && (
          <Segment basic loading={loading}>
            <CommentsTree
              comments={comments}
              count={this.state.count}
              loading={this.state.loading}
              editing={this.state.editing}
              approving={this.state.approving}
              deleting={this.state.deleting}
              approved={this.state.approved}
              deleted={this.state.deleted}
              editComment={this.editComment}
              approveComment={oid => {
                this.approveComments([oid]);
              }}
              deleteComment={oid => {
                this.deleteComments([oid]);
              }}
              checkedForApproval={this.state.checkedForApproval}
              checkedForDelete={this.state.checkedForDelete}
              setCheckedForApproval={(oid, toggle) => {
                const checkedForApproval = Object.assign(
                  {},
                  this.state.checkedForApproval
                );
                checkedForApproval[oid] = toggle;
                this.setState({ checkedForApproval });
              }}
              setCheckedForDelete={(oid, toggle) => {
                const checkedForDelete = Object.assign(
                  {},
                  this.state.checkedForDelete
                );
                checkedForDelete[oid] = toggle;
                this.setState({ checkedForDelete });
              }}
              setEditing={oid => {
                const editing = Object.assign({}, this.state.editing);
                editing[oid] = !editing[oid];
                this.setState({ editing });
              }}
              updateFilterSearch={search => {
                // const ref = this.refs.q.inputRef;
                // let {search}=this.state
                // if (search.includes(newSearch)) {
                //   search = search.replace(newSearch, '')

                // }
                // if (ref.value && ref.value.includes(search)) {
                //   ref.value = ref.value.replace(search, '');
                //   search = ref.value;
                // } else {
                //   ref.value += ` ${search}`;
                //   ref.value = ref.value.trim();
                //   search = ref.value;
                // }
                this.setState({ search }, this.fetchComments);
              }}
            />
          </Segment>
        )}

        {countries && countries.length && !loading ? (
          <ShowCountries countries={countries} />
        ) : null}

        {comments && !loading && (
          <Button
            fluid
            type="text"
            onClick={event => {
              this.fetchComments(true);
              window.scrollTo(0, 0);
            }}
          >
            Load more... (older than {this.state.oldest})
          </Button>
        )}
      </Container>
    );
  }
}

export default Comments;

class FilterForm extends React.Component {
  state = {
    search: this.props.search || ''
  };

  componentDidUpdate(prevProps) {
    if (prevProps.search !== this.props.search) {
      this.setState({
        search: this.props.search
      });
    }
  }

  render() {
    return (
      <form
        onSubmit={event => {
          event.preventDefault();
          const { search } = this.state;
          this.props.update({ search });
        }}
      >
        <Input
          action={{ icon: 'search' }}
          fluid
          value={this.state.search}
          placeholder="Search filter..."
          onChange={(event, data) => {
            this.setState({ search: data.value });
          }}
        />
        <Select
          placeholder="Approval filter options"
          value={
            this.props.unapprovedOnly
              ? 'unapproved'
              : this.props.autoapprovedOnly
              ? 'autoapproved'
              : ''
          }
          onChange={(event, data) => {
            let unapprovedOnly = false;
            let autoapprovedOnly = false;
            if (data.value === 'unapproved') {
              unapprovedOnly = true;
            } else if (data.value === 'autoapproved') {
              autoapprovedOnly = true;
            }
            this.props.update({ unapprovedOnly, autoapprovedOnly });
          }}
          options={[
            { key: '', value: '', text: 'Any' },
            { key: 'unapproved', value: 'unapproved', text: 'Unapproved only' },
            {
              key: 'autoapproved',
              value: 'autoapproved',
              text: 'Autoapproved only'
            }
          ]}
        />
      </form>
    );
  }
}

class Checked extends React.Component {
  render() {
    const {
      checkedForApproval,
      checkedForDelete,
      approveComments,
      deleteComments
    } = this.props;
    const oidsForApproval = Object.entries(checkedForApproval)
      .filter(([_, value]) => value)
      .map(([key, _]) => key);
    const oidsForDelete = Object.entries(checkedForDelete)
      .filter(([_, value]) => value)
      .map(([key, _]) => key);
    if (!oidsForApproval.length && !oidsForDelete.length) return null;
    return (
      <Message>
        <Message.Header>Batch Operation</Message.Header>
        <Button.Group widths="2">
          {oidsForApproval.length && (
            <Button
              positive
              type="text"
              onClick={event => {
                approveComments(oidsForApproval);
              }}
            >
              Approve all ({oidsForApproval.length})
            </Button>
          )}

          {oidsForDelete.length && (
            <Button
              negative
              type="text"
              onClick={event => {
                deleteComments(oidsForDelete);
              }}
            >
              Delete all ({oidsForDelete.length})
            </Button>
          )}
        </Button.Group>
      </Message>
    );
  }
}

class CommentsTree extends React.PureComponent {
  render() {
    const { comments, count, updateFilterSearch } = this.props;

    let lastBlogitem = null;
    return (
      <Comment.Group>
        <Header as="h2" dividing>
          {count.toLocaleString()} Comments
        </Header>

        {comments.map(comment => {
          const differentBlogitem = lastBlogitem !== comment.blogitem.id;
          lastBlogitem = comment.blogitem.id;
          return (
            <CommentTree
              key={comment.id}
              comment={comment}
              root={true}
              showBlogitem={differentBlogitem}
              addToSearch={term => {
                updateFilterSearch(term);
              }}
              {...this.props}
            />
          );
        })}
      </Comment.Group>
    );
  }
}

class CommentTree extends React.PureComponent {
  static defaultProps = {
    root: false,
    showBlogitem: false
  };
  hotness = seconds => {
    if (seconds < 60) {
      return '🔥🔥🔥';
    } else if (seconds < 60 * 60) {
      return '🔥';
    } else if (seconds < 60 * 60 * 24) {
      return '🔥';
    }
    return '';
  };

  gravatarSrc = comment => {
    let default_ = `https://api.adorable.io/avatars/35/${comment.name ||
      comment.oid}.png`;
    if (comment.email) {
      return `https://www.gravatar.com/avatar/${md5(
        comment.email
      )}?d=${encodeURIComponent(default_)}&s=35`;
    }
    return default_;
  };

  bumpedIndicator = comment => {
    if (!comment._bumped) return null;
    const diff = formatDistance(
      parseISO(comment.add_date),
      parseISO(comment.modify_date)
    );
    const title = `Last modified ${comment.modify_date} (difference ${diff})`;
    return <Icon name="exclamation" color="purple" title={title} />;
  };

  render() {
    const {
      comment,
      root,
      showBlogitem,
      addToSearch,
      checkedForApproval,
      checkedForDelete,
      setCheckedForApproval,
      setCheckedForDelete,
      setEditing,
      editing,
      editComment,
      approveComment,
      deleteComment,
      deleted,
      approved,
      deleting,
      approving
    } = this.props;

    const showAvatars = !window.matchMedia('(max-width: 600px)').matches;

    return (
      <Comment>
        {root && showBlogitem && (
          <Header as="h4" dividing>
            <a
              href={BASE_URL + comment.blogitem._absolute_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              {comment.blogitem.title}
            </a>{' '}
            <Icon
              color="grey"
              style={{ display: 'inline', cursor: 'pointer' }}
              size="mini"
              name="search"
              onClick={event => {
                event.preventDefault();
                addToSearch(`blogitem:${comment.blogitem.oid}`);
              }}
            />
          </Header>
        )}

        {showAvatars && <Comment.Avatar src={this.gravatarSrc(comment)} />}
        <Comment.Content>
          <Comment.Author as="a">
            {comment.name || <i>No name</i>}{' '}
            {comment.email ? `<${comment.email}>` : <i>No email</i>}{' '}
            <ShowOtherCommentCount count={comment.user_other_comments_count} />{' '}
            {comment.location && comment.location.country_code && (
              <small>
                <Flag
                  name={comment.location.country_code.toLowerCase()}
                  title={JSON.stringify(comment.location, null, 2)}
                />{' '}
                {comment.location.city || <i>no city</i>},{' '}
                {comment.location.country_name || <i>no country</i>}
              </small>
            )}
          </Comment.Author>
          <Comment.Metadata>
            <div>
              {this.hotness(comment.age_seconds)}
              <a
                href={BASE_URL + comment._absolute_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                <DisplayDate date={comment.add_date} />
              </a>{' '}
              <small>
                <b>Page: {comment.page ? comment.page : 'Overflowing'}</b>
              </small>{' '}
              {this.bumpedIndicator(comment)}{' '}
              <small style={{ marginLeft: 10 }}>
                {comment.comment.length.toLocaleString()} characters
              </small>{' '}
              {comment.auto_approved && <b>Auto approved!</b>}
            </div>
          </Comment.Metadata>
          <Comment.Text>
            {editing[comment.oid] ? (
              <EditComment comment={comment} editComment={editComment} />
            ) : (
              <p dangerouslySetInnerHTML={{ __html: comment.rendered }} />
            )}

            {!comment.approved && !editing[comment.oid] && (
              <p>
                Clues: <code>{JSON.stringify(comment._clues)}</code>
                {!!Object.keys(comment._clues.good).length &&
                  !Object.keys(comment._clues.bad).length && (
                    <span
                      title="So good it would automatically approve!"
                      role="img"
                      aria-label="Party!"
                    >
                      🎉⭐️🚢
                    </span>
                  )}
              </p>
            )}
          </Comment.Text>
          <Comment.Actions style={{ fontSize: '1em' }}>
            <Comment.Action>
              {comment.replies.length}{' '}
              {comment.replies.length === 1 ? 'reply' : 'replies'}
            </Comment.Action>
            <Comment.Action>
              <Button
                type="checkbox"
                onClick={event => {
                  setEditing(comment.oid);
                }}
                size="mini"
              >
                {editing[comment.oid] ? 'Cancel' : 'Edit'}
              </Button>
            </Comment.Action>
            {!comment.approved && deleted[comment.oid] && (
              <b style={{ color: '#db2828' }}>Deleted!</b>
            )}
            {!comment.approved && approved[comment.oid] && (
              <b style={{ color: '#21ba45' }}>Approved!</b>
            )}
            {!comment.approved &&
              !(deleted[comment.oid] || approved[comment.oid]) && (
                <Comment.Action>
                  <Checkbox
                    value={comment.oid}
                    checked={!!checkedForApproval[comment.oid]}
                    onChange={(_, data) => {
                      setCheckedForApproval(comment.oid, data.checked);
                      if (data.checked) {
                        setCheckedForDelete(comment.oid, false);
                      }
                    }}
                    style={{ paddingRight: 30, paddingLeft: 10 }}
                  />
                  <Button
                    disabled={
                      deleted[comment.oid] ||
                      approved[comment.oid] ||
                      deleting[comment.oid]
                    }
                    positive
                    loading={!!approving[comment.oid]}
                    onClick={event => {
                      event.preventDefault();
                      approveComment(comment.oid);
                    }}
                  >
                    Approve
                  </Button>
                  <Button
                    disabled={
                      deleted[comment.oid] ||
                      approved[comment.oid] ||
                      approving[comment.oid]
                    }
                    negative
                    loading={!!deleting[comment.oid]}
                    onClick={event => {
                      event.preventDefault();
                      deleteComment(comment.oid);
                    }}
                  >
                    Delete
                  </Button>
                  <Checkbox
                    value={comment.oid}
                    checked={!!checkedForDelete[comment.oid]}
                    onChange={(_, data) => {
                      setCheckedForDelete(comment.oid, data.checked);
                      if (data.checked) {
                        setCheckedForApproval(comment.oid, false);
                      }
                    }}
                    style={{ paddingRight: 30, paddingLeft: 10 }}
                  />
                </Comment.Action>
              )}
          </Comment.Actions>
        </Comment.Content>

        {comment.replies.length ? (
          <Comment.Group>
            {comment.replies.map(reply => (
              <CommentTree
                comment={reply}
                key={reply.id}
                addToSearch={addToSearch}
                checkedForApproval={checkedForApproval}
                checkedForDelete={checkedForDelete}
                setCheckedForApproval={setCheckedForApproval}
                setCheckedForDelete={setCheckedForDelete}
                setEditing={setEditing}
                approveComment={approveComment}
                deleteComment={deleteComment}
                editComment={editComment}
                editing={editing}
                approving={approving}
                deleting={deleting}
                approved={approved}
                deleted={deleted}
              />
            ))}
          </Comment.Group>
        ) : null}
      </Comment>
    );
  }
}

function ShowOtherCommentCount({ count }) {
  if (!count) return null;
  let msg = `${count} other comment`;
  if (count > 1) {
    msg += 's';
  }
  return <small title={msg}>({count})</small>;
}

class EditComment extends React.PureComponent {
  state = {
    text: this.props.comment.comment,
    name: this.props.comment.name || '',
    email: this.props.comment.email || ''
  };
  render() {
    return (
      <Form
        onSubmit={event => {
          event.preventDefault();
          this.props.editComment(this.props.comment, {
            text: this.state.text,
            name: this.state.name,
            email: this.state.email
          });
        }}
      >
        <Input
          value={this.state.name}
          onChange={(_, data) => {
            this.setState({ name: data.value });
          }}
          placeholder="Name..."
        />
        <Input
          value={this.state.email}
          onChange={(_, data) => {
            this.setState({ email: data.value });
          }}
          placeholder="Email..."
        />
        <TextArea
          value={this.state.text}
          onChange={(_, data) => {
            this.setState({ text: data.value });
          }}
        />
        <Button primary>Save</Button>
      </Form>
    );
  }
}

class ShowCountries extends React.PureComponent {
  render() {
    const { countries } = this.props;
    return (
      <div style={{ marginBottom: 20 }}>
        <Header as="h3" dividing>
          Countries of Commenters
        </Header>
        <List>
          {countries.map(row => {
            return (
              <List.Item key={row.name}>
                <List.Content>
                  <List.Header>
                    {[...Array(row.count).keys()].map(i => (
                      <Flag
                        key={`${row.country_code}${i}`}
                        name={row.country_code.toLowerCase()}
                        title={`${row.count} from ${row.name}`}
                      />
                    ))}
                    {row.name} <small>({row.count})</small>
                  </List.Header>
                </List.Content>
              </List.Item>
            );
          })}
        </List>
      </div>
    );
  }
}
