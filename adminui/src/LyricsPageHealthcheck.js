import React, { useRef, useEffect, useState } from 'react';
import {
  Button,
  Container,
  Dimmer,
  Header,
  Icon,
  Loader,
  Segment,
  Select,
} from 'semantic-ui-react';
import useSWR from 'swr';
import { useWSS } from './WSSContext';
import { ShowServerError, useLocalStorage } from './Common';
import XCacheAnalyze from './XCacheAnalyze';

const xcacheAnalyzeLoopOptions = [...Array(5 + 1).keys()]
  .filter((n) => !!n)
  .map((n) => {
    return { key: n, value: n, text: `${n} time${n === 1 ? '' : 's'}` };
  });

const LOOP_SECONDS = 30;

function LyricsPageHealthcheck({ accessToken }) {
  const [nextFetch, setNextFetch] = useState(null);
  const { data, error } = useSWR(
    '/api/v0/lyrics-page-healthcheck',
    async (url) => {
      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      if (!response.ok) {
        throw new Error(`${response.status} on ${response.url}`);
      } else {
        return await response.json();
      }
    },
    {
      refreshInterval: LOOP_SECONDS * 1000,
      revalidateOnFocus: false,
    }
  );

  useEffect(() => {
    setNextFetch(new Date(new Date().getTime() + LOOP_SECONDS * 1000));
  }, [data, error]);

  const loading = !data && !error;

  const health = data ? data.health : null;
  return (
    <Container>
      <Header as="h1">Lyrics Page Healthcheck</Header>
      <ShowServerError error={error} />
      <Segment basic>
        <Dimmer active={loading} inverted>
          <Loader inverted>Loading</Loader>
        </Dimmer>
        {health && <ShowHealth health={health} accessToken={accessToken} />}
        {nextFetch && <ShowLoopCountdown nextFetch={nextFetch} />}
      </Segment>
    </Container>
  );
}

export default LyricsPageHealthcheck;

function ShowLoopCountdown({ nextFetch }) {
  const [left, updateLeft] = React.useState(
    Math.ceil((nextFetch.getTime() - new Date().getTime()) / 1000)
  );
  React.useEffect(() => {
    const loop = window.setInterval(() => {
      updateLeft(
        Math.ceil((nextFetch.getTime() - new Date().getTime()) / 1000)
      );
    }, 1000);
    return () => window.clearInterval(loop);
  }, [nextFetch]);

  if (left > 120) {
    return <small>Refreshing in {Math.floor(left / 60)} minutes.</small>;
  }
  if (left > 0) {
    return <small>Refreshing in {left} seconds.</small>;
  } else {
    return <small>Refreshing now.</small>;
  }
}

function ShowHealth({ health, accessToken }) {
  const [xcacheAnalyzeAll, setXCacheAnalyzeAll] = React.useState(null);
  const [loopsDone, setLoopsDone] = React.useState(0);
  const [
    maxXCacheAnalyzeAllLoops,
    setMaxXCacheAnalyzeAllLoops,
  ] = useLocalStorage('max-xcache-analyze-all-loops', 1);

  const [xcacheAnalysisDone, setXCacheAnalysisDone] = React.useState(0);
  const documentTitleRef = useRef(document.title);
  useEffect(() => {
    if (xcacheAnalysisDone) {
      document.title = `(${xcacheAnalysisDone}) ${documentTitleRef.current}`;
    } else {
      document.title = documentTitleRef.current;
    }
  }, [xcacheAnalysisDone]);

  function startAllXCacheAnalyze() {
    const todo = new Map();
    health.forEach((page, i) => {
      todo.set(page.url, i === 0);
    });
    setXCacheAnalyzeAll(todo);
  }

  function stopAllXCacheAnalyze() {
    // setXCacheAnalyzeAll(null);
    // setXCacheAnalysisDone(0);
    // setLoopsDone(0);
  }

  // function nextAllXCacheAnalyze(url) {
  //   if (xcacheAnalyzeAll === null) {
  //     // It has been stopped!
  //     return;
  //   }
  //   const todo = new Map();
  //   let first = true;
  //   for (let u of xcacheAnalyzeAll.keys()) {
  //     if (u !== url) {
  //       todo.set(u, first);
  //       first = false;
  //     }
  //   }
  //   if (!todo.size) {
  //     // Start over!
  //     if (loopsDone + 1 < maxXCacheAnalyzeAllLoops) {
  //       health.forEach((page, i) => {
  //         todo.set(page.url, i === 0);
  //       });
  //     } else {
  //       setXCacheAnalyzeAll(null);
  //       return;
  //     }
  //     setLoopsDone(loopsDone + 1);
  //   }
  //   setXCacheAnalyzeAll(todo);
  // }

  // function isAutoStart(url) {
  //   if (xcacheAnalyzeAll) {
  //     return xcacheAnalyzeAll.get(url) || false;
  //   }
  //   return false;
  // }

  const { register } = useWSS();
  useEffect(() => {
    register((data) => {
      const newMap = new Map(Object.entries(data.xcache_todo));

      if (newMap.size) {
        setXCacheAnalyzeAll(newMap);
      } else {
        setXCacheAnalyzeAll(null);
      }
    }, 'xcache_todo');
  }, [register]);

  return (
    <div>
      <div style={{ textAlign: 'right' }}>
        <Button
          onClick={() => {
            startAllXCacheAnalyze();
          }}
          disabled={!!xcacheAnalyzeAll}
        >
          X-Cache Analyze All
        </Button>
        {!!xcacheAnalyzeAll && (
          <Button onClick={() => stopAllXCacheAnalyze()}>Stop</Button>
        )}
        {!!xcacheAnalyzeAll && (
          <div>
            Max. loops
            <Select
              placeholder="Max. loops"
              options={xcacheAnalyzeLoopOptions}
              onChange={(event, data) =>
                setMaxXCacheAnalyzeAllLoops(data.value)
              }
              value={maxXCacheAnalyzeAllLoops}
            />
            <br />
            Loops done: {loopsDone}
            {loopsDone >= maxXCacheAnalyzeAllLoops ? (
              <p>
                <b>Stopped after {loopsDone} loops!</b>
              </p>
            ) : null}
          </div>
        )}
      </div>

      {xcacheAnalyzeAll && (
        <ShowCurrentXCacheAnalysisURL todo={xcacheAnalyzeAll} />
      )}

      <Segment.Group>
        {health.map((page) => {
          let color = '';
          let name = '';
          if (page.health === 'WARNING') {
            color = 'orange';
            name = 'warning sign';
          } else if (page.health === 'ERROR') {
            color = 'red';
            name = 'thumbs down';
          } else if (page.health === 'OK') {
            color = 'green';
            name = 'thumbs up';
          } else {
            throw new Error(`Unrecognized enum ${page.health}`);
          }
          return (
            <Segment key={page.url}>
              <a href={page.url}>{page.url}</a>{' '}
              <a
                href={`/cdn?url=${encodeURI(page.url)}`}
                rel="noopener noreferrer"
                target="_blank"
                title="Do a CDN probe"
              >
                <small>(CDN probe)</small>
              </a>{' '}
              <Icon name={name} color={color} size="large" />{' '}
              <small>took {`${(1000 * page.took).toFixed(1)}ms`}</small>
              {page.errors && page.errors.length ? (
                <ShowErrors errors={page.errors} />
              ) : null}{' '}
              <XCacheAnalyze
                accessToken={accessToken}
                url={page.url}
                // start={isAutoStart(page.url)}
                // finished={(error) => {
                //   if (!error) {
                //     nextAllXCacheAnalyze(page.url);
                //     setXCacheAnalysisDone(xcacheAnalysisDone + 1);
                //   }
                // }}
                minimalButton={true}
              />
            </Segment>
          );
        })}
      </Segment.Group>
    </div>
  );
}

function ShowErrors({ errors }) {
  return (
    <div>
      {errors.map((error, i) => (
        <p key={i}>{error}</p>
      ))}
    </div>
  );
}

function ShowCurrentXCacheAnalysisURL({ todo }) {
  let current = '';
  let left = 0;
  for (let u of todo.keys()) {
    if (todo.get(u)) {
      current = u;
    } else {
      left++;
    }
  }
  return (
    <p>
      Currently x-cache checking <a href={current}>{current}</a> ({left} left)
    </p>
  );
}
