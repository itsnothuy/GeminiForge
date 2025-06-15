import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import HomePage from './frontend/src/pages/HomePage';
import ProductPage from './frontend/src/pages/ProductPage';
import App from './frontend/src/App';
import axios from 'axios';

jest.mock('axios');

describe('HomePage Component', () => {
  test('renders welcome message', () => {
    render(
      <BrowserRouter>
        <HomePage />
      </BrowserRouter>
    );
    const welcomeElement = screen.getByText(/Welcome to the Ecommerce Platform/i);
    expect(welcomeElement).toBeInTheDocument();
  });
});

describe('ProductPage Component', () => {
  const mockProduct = {
    id: 1,
    name: 'Test Product',
    description: 'Test Description',
    price: 99.99,
  };

  beforeEach(() => {
    axios.get.mockResolvedValue({ data: mockProduct });
  });

  test('fetches and displays product details', async () => {
    render(
      <BrowserRouter>
        <Routes>
          <Route path="/product/:id" element={<ProductPage />} />
        </Routes>
      </BrowserRouter>,
      { wrapper: BrowserRouter }
    );

    // Simulate route params
    window.history.pushState({}, 'Product Page', '/product/1');

    await waitFor(() => screen.getByText(/Test Product/i));

    const nameElement = screen.getByText(/Test Product/i);
    const descriptionElement = screen.getByText(/Test Description/i);
    const priceElement = screen.getByText(/99.99/i);

    expect(nameElement).toBeInTheDocument();
    expect(descriptionElement).toBeInTheDocument();
    expect(priceElement).toBeInTheDocument();
  });

  test('displays loading message initially', () => {
    render(
      <BrowserRouter>
        <Routes>
          <Route path="/product/:id" element={<ProductPage />} />
        </Routes>
      </BrowserRouter>,
      { wrapper: BrowserRouter }
    );

    window.history.pushState({}, 'Product Page', '/product/1');
    const loadingElement = screen.getByText(/Loading.../i);
    expect(loadingElement).toBeInTheDocument();
  });

  test('displays error message on API failure', async () => {
    axios.get.mockRejectedValue(new Error('API Error'));
    render(
      <BrowserRouter>
        <Routes>
          <Route path="/product/:id" element={<ProductPage />} />
        </Routes>
      </BrowserRouter>,
      { wrapper: BrowserRouter }
    );

    window.history.pushState({}, 'Product Page', '/product/1');

    await waitFor(() => screen.getByText(/Error:/i));
    const errorElement = screen.getByText(/Error: API Error/i);
    expect(errorElement).toBeInTheDocument();
  });
});

describe('App Component', () => {
  test('renders HomePage when navigating to /', () => {
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>
    );
    window.history.pushState({}, 'Home Page', '/');
    const homePageElement = screen.getByText(/Welcome to the Ecommerce Platform/i);
    expect(homePageElement).toBeInTheDocument();
  });

  test('renders ProductPage when navigating to /product/:id', async () => {
    const mockProduct = {
      id: 1,
      name: 'Test Product',
      description: 'Test Description',
      price: 99.99,
    };
    axios.get.mockResolvedValue({ data: mockProduct });

    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>
    );
    window.history.pushState({}, 'Product Page', '/product/1');

    await waitFor(() => screen.getByText(/Test Product/i));
    const productPageElement = screen.getByText(/Test Product/i);
    expect(productPageElement).toBeInTheDocument();
  });
});