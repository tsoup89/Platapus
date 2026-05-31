import axios from 'axios';
import { getBackendUrl } from '../storage/config';

const client = axios.create({ timeout: 10_000 });

// Resolve the base URL from AsyncStorage on each request
client.interceptors.request.use(async (config) => {
  if (!config.baseURL) {
    const url = await getBackendUrl();
    if (url) config.baseURL = `${url}/api`;
  }
  return config;
});

export default client;
