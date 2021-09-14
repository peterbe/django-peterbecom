import React from 'react';
import {
  Button,
  Container,
  Image,
  Input,
  Loader,
  Card,
} from 'semantic-ui-react';

import { formatFileSize, BlogitemBreadcrumb, ShowServerError } from './Common';

class UploadImages extends React.Component {
  state = {
    images: null,
    loading: false,
    serverError: null,
    previewUrls: [],
  };

  componentDidMount() {
    document.title = 'Upload Images';
  }

  fileChange = async (event) => {
    const files = Array.from(event.target.files);

    files.forEach(async (file, i) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        // console.log(file);
        // console.log(reader);
        this.setState((state) => {
          const previewUrls = [...state.previewUrls].concat({
            name: file.name,
            file,
            url: reader.result,
            uploaded: false,
            uploading: false,
            errored: false,
          });
          return { previewUrls };
        });
      };
      reader.readAsDataURL(file);
    });
  };

  fileUpload = async (preview, title) => {
    const { oid } = this.props.match.params;

    const formData = new FormData();

    formData.append('file', preview.file);
    formData.append('title', title);

    try {
      const response = await fetch(`/api/v0/plog/${oid}/images`, {
        method: 'POST',
        body: formData,
        // headers: {
        //   Authorization: `Bearer ${this.props.accessToken}`,
        // },
      });
      if (response.ok) {
        const result = await response.json();
        this.setState((state) => {
          const previewUrls = state.previewUrls.map((each) => {
            if (each.name === preview.file.name) {
              each.uploaded = result.id;
            }
            return each;
          });
          return { previewUrls };
        });
      } else {
        this.setState({ serverError: response });
        this.setState((state) => {
          const previewUrls = state.previewUrls.map((each) => {
            if (each.name === preview.file.name) {
              each.errored = true;
            }
            return each;
          });
          return { previewUrls };
        });
      }
    } catch (ex) {
      this.setState({ serverError: ex });
    }
  };

  undoUpload = async (preview) => {
    const { oid } = this.props.match.params;
    try {
      let url = `/api/v0/plog/${oid}/images?id=${preview.uploaded}`;
      const response = await fetch(url, {
        method: 'DELETE',
        // headers: {
        //   Authorization: `Bearer ${this.props.accessToken}`,
        // },
      });
      if (response.ok) {
        // const result = await response.json();
        this.setState((state) => {
          const previewUrls = state.previewUrls.filter((each) => {
            return each.name !== preview.file.name;
          });
          return { previewUrls };
        });
      } else {
        this.setState({ serverError: response });
      }
    } catch (ex) {
      this.setState({ serverError: ex });
    }
  };

  cancelUpload = (preview) => {
    this.setState((state) => {
      const previewUrls = state.previewUrls.filter((each) => {
        return each.name !== preview.file.name;
      });
      return { previewUrls };
    });
  };

  render() {
    const { loading, serverError } = this.state;
    const oid = this.props.match.params.oid;
    if (!serverError && loading) {
      return (
        <Container>
          <Loader
            active
            size="massive"
            inline="centered"
            content="Uploading..."
            style={{ margin: '200px 0' }}
          />
        </Container>
      );
    }
    return (
      <Container>
        <BlogitemBreadcrumb oid={oid} page="images" />

        <ShowServerError error={this.state.serverError} />
        <form>
          <h1>Upload Images</h1>

          <input type="file" multiple onChange={this.fileChange} />

          {this.state.previewUrls.map((each) => {
            return (
              <PreviewCard
                preview={each}
                key={each.file.name}
                undoUpload={this.undoUpload}
                fileUpload={this.fileUpload}
                canelUpload={this.cancelUpload}
              />
            );
          })}
        </form>
      </Container>
    );
  }
}

export default UploadImages;

class PreviewCard extends React.Component {
  state = { title: '' };
  render() {
    const { preview } = this.props;
    return (
      <Card.Group key={preview.file.name}>
        <Card>
          <Image src={preview.url} />
          <Card.Content>
            <Card.Header>{preview.file.name}</Card.Header>
            <Card.Meta>
              {preview.file.type} {formatFileSize(preview.file.size)}
            </Card.Meta>
            <Card.Description />
            <Input
              value={this.state.title}
              placeholder="Title..."
              fluid
              onChange={(event) => {
                this.setState({ title: event.target.value });
              }}
            />
          </Card.Content>
          <Card.Content extra>
            {preview.uploaded ? (
              <Button
                onClick={(event) => {
                  event.preventDefault();
                  this.props.undoUpload(preview);
                }}
              >
                Undo upload
              </Button>
            ) : (
              <>
                <Button
                  primary={true}
                  onClick={(event) => {
                    event.preventDefault();
                    this.props.fileUpload(preview, this.state.title);
                  }}
                >
                  Upload
                </Button>
                <Button
                  onClick={(event) => {
                    event.preventDefault();
                    this.props.canelUpload(preview);
                  }}
                >
                  Cancel
                </Button>
              </>
            )}

            {preview.uploading && !preview.errored && (
              <Loader active inline="centered" />
            )}

            {preview.errored && <b style={{ color: 'red' }}>Error</b>}
          </Card.Content>
        </Card>
      </Card.Group>
    );
  }
}
