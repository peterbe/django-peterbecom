import React from 'react';
import {
  Button,
  Card,
  Message,
  Container,
  Breadcrumb,
  Image,
  Loader,
  Icon,
  Input,
  Form,
  Checkbox,
  TextArea,
  Select
} from 'semantic-ui-react';
import { Link } from 'react-router-dom';
import { addHours } from 'date-fns/esm';
import { CopyToClipboard } from 'react-copy-to-clipboard';

import { DisplayDate, ShowServerError, BlogitemBreadcrumb } from './Common';
import { BASE_URL } from './Config';

export class EditBlogitem extends React.Component {
  state = {
    blogitem: null,
    allCategories: null,
    serverError: null,
    updated: null,
    validationErrors: null,
    preview: null
  };
  componentDidMount() {
    document.title = 'Edit Blogitem';

    this.fetchBlogitem(this.props.match.params.oid, this.props.accessToken);
    this.fetchAllCategories(this.props.accessToken);
  }

  fetchAllCategories = async accessToken => {
    const cacheKey = 'allCategories';
    const allCategories = localStorage.getItem(cacheKey);
    if (allCategories) {
      this.setState({ allCategories: JSON.parse(allCategories) });
    }
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    try {
      const response = await fetch('/api/v0/categories', {
        headers: {
          Authorization: `Bearer ${this.props.accessToken}`
        }
      });
      if (response.ok) {
        const json = await response.json();
        this.setState({ allCategories: json.categories }, () => {
          localStorage.setItem(
            cacheKey,
            JSON.stringify(this.state.allCategories)
          );
        });
      } else {
        this.setState({ serverError: response });
      }
    } catch (ex) {
      this.setState({ serverError: ex });
    }
  };

  fetchBlogitem = async (oid, accessToken) => {
    try {
      const response = await fetch(`/api/v0/plog/${encodeURIComponent(oid)}`, {
        headers: {
          Authorization: `Bearer ${accessToken}`
        }
      });
      if (response.ok) {
        const json = await response.json();
        this.setState({ blogitem: json.blogitem });
      } else {
        this.setState({ serverError: response });
      }
    } catch (ex) {
      this.setState({ serverError: ex });
    }
  };

  previewBlogitem = async (data, accessToken) => {
    if (!accessToken) {
      throw new Error('No accessToken');
    }
    const response = await fetch(`/api/v0/plog/preview/`, {
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
      this.setState({ preview: data.blogitem });
    } else {
      this.setState({ serverError: response.status });
    }
  };

  updateBlogitem = async data => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    const oid = this.state.blogitem.oid;
    const response = await fetch(`/api/v0/plog/${oid}`, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        Authorization: `Bearer ${this.props.accessToken}`
      },
      body: JSON.stringify(data)
    });
    if (response.ok) {
      const data = await response.json();
      const newOid = data.blogitem.oid !== this.state.blogitem.oid;
      this.setState({
        blogitem: data.blogitem,
        updated: new Date(),
        validationErrors: null
      });
      if (newOid) {
        window.location.href = `/plog/${data.blogitem.oid}`;
      }
    } else if (response.status === 400) {
      const data = await response.json();
      this.setState({ serverError: null, validationErrors: data.errors });
    } else {
      this.setState({ serverError: response.status });
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
    const { blogitem } = this.state;
    if (!this.state.serverError && !blogitem) {
      return (
        <Container>
          <Loader
            active
            size="massive"
            inline="centered"
            content="Loading Blogitem..."
            style={{ margin: '200px 0' }}
          />
        </Container>
      );
    }
    return (
      <Container>
        <BlogitemBreadcrumb blogitem={blogitem} page="edit" />
        <ShowServerError error={this.state.serverError} />
        {this.renderUpdated()}
        {this.state.validationErrors && (
          <Message negative>
            <Message.Header>Validation Errors</Message.Header>
            <div>
              <pre>
                {JSON.stringify(this.state.validationErrors, undefined, 2)}
              </pre>
            </div>
          </Message>
        )}
        {this.state.blogitem && (
          <EditForm
            accessToken={this.props.accessToken}
            blogitem={blogitem}
            allCategories={this.state.allCategories}
            validationErrors={this.state.validationErrors}
            // accessToken={this.props.accessToken}
            onLoadPreview={async data => {
              // store.blogitems.previewBlogitem(data, store.user.accessToken);
              this.previewBlogitem(data, this.props.accessToken);
            }}
            onSubmitData={data => {
              this.setState({ updated: null });
              this.updateBlogitem(data, this.props.accessToken);
              // store.blogitems.updateBlogitem(
              //   store.blogitems.blogitem.id,
              //   data,
              //   store.user.accessToken
              // );
            }}
          />
        )}
        {this.renderUpdated()}
        <PreviewBlogitem data={this.state.preview} />
        {/* {store.blogitems.preview && store.blogitems.preview} */}
      </Container>
    );
  }
}

export class AddBlogitem extends EditBlogitem {
  componentDidMount() {
    document.title = 'Add Blogitem';

    if (this.props.accessToken) {
      this.fetchAllCategories(this.props.accessToken);
    }
  }

  componentDidUpdate(prevProps) {
    if (prevProps.accessToken !== this.props.accessToken) {
      this.fetchAllCategories(this.props.accessToken);
    }
  }

  createBlogitem = async data => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    const response = await fetch(`/api/v0/plog/`, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        Authorization: `Bearer ${this.props.accessToken}`
      },
      body: JSON.stringify(data)
    });
    if (response.ok) {
      const data = await response.json();
      this.setState(
        { updated: new Date(), validationErrors: null, serverError: null },
        () => {
          window.location.href = `/plog/${data.blogitem.oid}`;
        }
      );
    } else if (response.status === 400) {
      const data = await response.json();
      this.setState({ validationErrors: data.errors, serverError: null });
    } else {
      this.setState({ serverError: response.status });
    }
  };

  render() {
    const defaultPubDate = addHours(new Date(), 1);

    const blogitemSkeleton = {
      oid: '',
      title: '',
      summary: '',
      text: '',
      url: '',
      // pub_date: format(new Date(), 'YYYY-MM-dd HH:MM:ss'),
      pub_date: defaultPubDate.toISOString(),
      display_format: 'markdown',
      categories: [],
      keywords: []
    };
    return (
      <Container>
        <Breadcrumb>
          <Breadcrumb.Section>
            <Link to="/plog">Blogitems</Link>
          </Breadcrumb.Section>
          <Breadcrumb.Divider />
          <Breadcrumb.Section active>Add</Breadcrumb.Section>
        </Breadcrumb>
        <ShowServerError error={this.state.serverError} />
        {this.renderUpdated()}
        {this.state.validationErrors && (
          <Message negative>
            <Message.Header>Validation Errors</Message.Header>
            <div>
              <pre>
                {JSON.stringify(this.state.validationErrors, undefined, 2)}
              </pre>
            </div>
          </Message>
        )}
        <EditForm
          blogitem={blogitemSkeleton}
          allCategories={this.state.allCategories}
          // accessToken={store.user.accessToken}
          validationErrors={this.state.validationErrors}
          onLoadPreview={async data => {
            // this.previewBlogitem(data);
          }}
          onSubmitData={async data => {
            this.setState({ updated: null });
            this.createBlogitem(data);
          }}
        />
        {this.renderUpdated()}
      </Container>
    );
  }
}

function slugify(s) {
  return s
    .trim()
    .replace(/\s+/gi, '-')
    .replace(/'/g, '')
    .toLowerCase();
}

class EditForm extends React.PureComponent {
  state = {
    hideLabels: JSON.parse(localStorage.getItem('hideLabels') || 'false'),
    showUnimportantFields: false,
    saving: false,
    categories: null
  };

  componentDidMount() {
    this.setRefs(this.props.blogitem);
    this.setCategories(this.props.blogitem.categories);
  }

  componentDidUpdate(prevProps) {
    if (prevProps.blogitem !== this.props.blogitem) {
      this.setRefs(this.props.blogitem);
      this.setCategories(this.props.blogitem.categories);
    }
  }
  setRefs = blogitem => {
    const simpleKeys = ['oid', 'title', 'url', 'pub_date'];
    simpleKeys.forEach(key => {
      this.refs[key].inputRef.value = blogitem[key];
    });
    this.refs.text.ref.value = blogitem.text;
    this.refs.summary.ref.value = blogitem.summary;
    this.refs.keywords.ref.value = blogitem.keywords.join('\n');
  };

  setCategories = categories => {
    this.setState({ categories: categories.map(category => category.id) });
    // this.categories = categories;
  };

  onTextBlur = event => {
    event.preventDefault();
    this._submit(true);
  };

  submitForm = event => {
    event.preventDefault();
    this._submit();
  };

  _submit = (preview = false) => {
    const { blogitem } = this.props;
    const data = {};
    // data.title = this.state.title;
    // const simpleKeys = ['oid', 'title', 'url', 'pub_date'];
    const simpleKeys = ['oid', 'title', 'url', 'pub_date'];
    simpleKeys.forEach(key => {
      data[key] = this.refs[key].inputRef.value;
    });
    data.text = this.refs.text.ref.value;
    data.summary = this.refs.summary.ref.value;

    data.categories = this.state.categories;
    data.keywords = this.refs.keywords.ref.value.trim().split(/\s*[\r\n]+\s*/g);
    data.display_format = this.displayFormat
      ? this.displayFormat.value
      : blogitem.display_format;
    data.codesyntax = this.codesyntax
      ? this.codesyntax.value
      : blogitem.codesyntax;
    data.disallow_comments = this.disallowComments
      ? this.disallowComments.checked
      : blogitem.disallow_comments;
    data.hide_comments = this.hideComments
      ? this.hideComments.checked
      : blogitem.hide_comments;

    if (preview) {
      this.props.onLoadPreview(data);
    } else {
      this.props.onSubmitData(data);
    }
  };

  // Assume the OID input field has not been manually edited.
  oidTouched = false;

  render() {
    const { blogitem, allCategories } = this.props;
    const { hideLabels, showUnimportantFields } = this.state;
    let { validationErrors } = this.props;
    if (!validationErrors) {
      validationErrors = {};
    }

    let categoryOptions = [];
    if (allCategories) {
      categoryOptions = allCategories.map(cat => ({
        key: cat.id,
        text: `${cat.name} (${cat.count})`,
        name: cat.name,
        value: cat.id
      }));
    }
    const keywords = blogitem.keywords.map(keyword => keyword);
    this.categories = blogitem.categories.map(category => category.id);
    const displayFormat = blogitem.display_format;
    const displayFormatOptions = ['markdown', 'structuredtext'].map(o => {
      return { key: o, text: o, name: o, value: o };
    });

    return (
      <Form onSubmit={this.submitForm}>
        <h3>
          <a href={BASE_URL + blogitem._absolute_url}>{blogitem.title}</a>
        </h3>
        <Thumbnails accessToken={this.props.accessToken} oid={blogitem.oid} />
        <p style={{ textAlign: 'right' }}>
          <Button
            size="mini"
            secondary={!this.state.hideLabels}
            onClick={event => {
              event.preventDefault();
              this.setState({ hideLabels: !this.state.hideLabels }, () => {
                localStorage.setItem(
                  'hideLabels',
                  JSON.stringify(this.state.hideLabels)
                );
              });
            }}
          >
            {hideLabels ? 'Show labels' : 'Hide labels'}
          </Button>
          <Button
            size="mini"
            secondary={showUnimportantFields}
            onClick={event => {
              event.preventDefault();
              this.setState({
                showUnimportantFields: !showUnimportantFields
              });
            }}
          >
            {showUnimportantFields ? 'Hide some fields' : 'Show all fields'}
          </Button>
        </p>
        <Form.Field>
          {!hideLabels ? <label>OID</label> : null}
          <Input
            ref="oid"
            error={!!validationErrors.oid}
            onChange={event => {
              if (!this.oidTouched) {
                this.oidTouched = true;
              }
            }}
          />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>Title</label> : null}
          <Input
            ref="title"
            error={!!validationErrors.title}
            onChange={event => {
              if (!this.oidTouched && !this.props.blogitem.oid) {
                this.refs.oid.inputRef.value = slugify(event.target.value);
              }
            }}
          />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>Text</label> : null}
          <TextArea
            ref="text"
            className="monospaced"
            rows={25}
            onBlur={this.onTextBlur}
            style={{ overscrollBehaviorY: 'contain' }}
          />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>Summary</label> : null}
          <TextArea ref="summary" rows={4} />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>URL</label> : null}
          <Input ref="url" placeholder="URL" />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>Pub Date</label> : null}
          <Input
            ref="pub_date"
            placeholder="Pub date"
            error={!!validationErrors.pub_date}
          />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>Categories</label> : null}
          <Select
            value={this.state.categories}
            options={categoryOptions}
            selection
            multiple
            onChange={(event, data) => {
              this.setState({ categories: data.value });
            }}
            renderLabel={item => item.name}
          />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>Keywords</label> : null}
          <TextArea
            ref="keywords"
            placeholder="Keywords"
            rows={5}
            defaultValue={keywords.join('\n')}
          />
        </Form.Field>
        {showUnimportantFields ? (
          <Form.Field>
            {!hideLabels ? <label>Display Format</label> : null}
            <Select
              error={!!validationErrors.display_format}
              options={displayFormatOptions}
              selection
              onChange={(event, data) => {
                this.displayFormat = data;
              }}
              renderLabel={item => item.name}
              defaultValue={displayFormat}
            />
          </Form.Field>
        ) : null}
        {showUnimportantFields ? (
          <Form.Field>
            {!hideLabels ? <label>Code Syntax</label> : null}
            <Input
              placeholder="Code Syntax"
              onChange={(event, data) => {
                this.codesyntax = data;
              }}
              defaultValue={blogitem.codesyntax}
            />
          </Form.Field>
        ) : null}
        {showUnimportantFields ? (
          <Form.Field>
            <Checkbox
              label="Disallow comments"
              ref="disallow_comments"
              onChange={(event, data) => {
                this.disallowComments = data;
              }}
              defaultChecked={!!blogitem.disallow_comments}
            />
          </Form.Field>
        ) : null}
        {showUnimportantFields ? (
          <Form.Field>
            <Checkbox
              label="Hide comments"
              ref="hide_comments"
              onChange={(event, data) => {
                this.hideComments = data;
              }}
              defaultChecked={!!blogitem.hide_comments}
            />
          </Form.Field>
        ) : null}
        <Button
          type="submit"
          primary={true}
          loading={this.state.saving}
          onClick={() => {
            this.setState({ saving: true }, () => {
              window.setTimeout(() => {
                if (!this.dismounted) {
                  this.setState({ saving: false });
                }
              }, 2000);
            });
          }}
        >
          Save Changes
        </Button>
      </Form>
    );
  }
}

class PreviewBlogitem extends React.PureComponent {
  render() {
    const { data } = this.props;
    if (!data) {
      return null;
    }
    return (
      <div className="preview">
        <h3>PREVIEW</h3>
        <div
          dangerouslySetInnerHTML={{
            __html: data.html
          }}
        />
      </div>
    );
  }
}

class Thumbnails extends React.PureComponent {
  state = { copied: null, show: false, images: null };

  async componentDidMount() {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    const oid = this.props.oid;
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
  }
  setCopied = key => {
    this.setState({ copied: key }, () => {
      if (this.timeout) {
        window.clearTimeout(this.timeout);
      }
      this.timeout = window.setTimeout(() => {
        if (!this.dismounted) {
          this.setState({ copied: false });
        }
      }, 3000);
    });
  };
  render() {
    if (!this.state.show && !this.state.images) {
      return null;
    }
    if (!this.state.show && this.state.images) {
      if (!this.state.images.length) {
        return null;
      }
      return (
        <Button
          onClick={event => {
            this.setState({ show: true });
          }}
        >
          Show ({this.state.images.length}) thumbnails
        </Button>
      );
    }
    const { images } = this.state;
    const keys = ['small', 'big', 'bigger'];
    return (
      <div>
        <Button
          onClick={event => {
            this.setState({ show: false });
          }}
        >
          Hide thumbnails
        </Button>
        {images.map(image => {
          // console.log(image);
          return (
            <Card.Group key={image.full_url}>
              {keys.map(key => {
                const thumb = image[key];

                const imageTagHtml = `
                <img src="${thumb.url}" alt="${thumb.alt}" width="${
                  thumb.width
                }" height="${thumb.height}">
                `.trim();
                const aTagHtml = `
                <a href="${image.full_url}">${imageTagHtml.replace(
                  'width=',
                  'class="floatright" width='
                )}</a>
                `.trim();
                return (
                  <Card key={key}>
                    <a href={BASE_URL + thumb.url}>
                      <Image src={BASE_URL + thumb.url} />
                    </a>
                    <Card.Content>
                      <Card.Header>{key}</Card.Header>
                      <Card.Meta>
                        <span className="date">{`${thumb.width}x${
                          thumb.height
                        }`}</span>
                      </Card.Meta>
                      <Card.Description>{thumb.alt}</Card.Description>
                      {this.state.copied === key ? (
                        <small>copied!</small>
                      ) : null}
                    </Card.Content>
                    <Card.Content extra>
                      <Icon name="copy" loading={this.state.copied === key} />
                      <CopyToClipboard
                        text={thumb.url}
                        onCopy={() => this.setCopied(key)}
                      >
                        <Button size="mini">URL</Button>
                      </CopyToClipboard>
                      <CopyToClipboard
                        text={imageTagHtml}
                        onCopy={() => this.setCopied(key)}
                      >
                        <Button size="mini">Image tag</Button>
                      </CopyToClipboard>
                      <CopyToClipboard
                        text={aTagHtml}
                        onCopy={() => this.setCopied(key)}
                      >
                        <Button size="mini">Whole tag</Button>
                      </CopyToClipboard>
                    </Card.Content>
                  </Card>
                );
              })}
            </Card.Group>
          );
        })}
      </div>
    );
  }
}
