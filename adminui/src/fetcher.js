export const fetcher = async (url) => {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${response.status} on ${url}`);
  }
  return await response.json();
};
