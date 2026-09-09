export const USER_ROLES = {
  ADMIN: 'ADMIN',
  INSPECTOR: 'INSPECTOR',
  REVIEWER: 'REVIEWER',
};

export const ROLE_ROUTE_PERMISSIONS = {
  ADMIN: [
    '/dashboard',
    '/scans/new',
    '/products',
    '/products/:id',
    '/inspections/:id',
    '/reports',
    '/rules',
  ],
  INSPECTOR: [
    '/dashboard',
    '/scans/new',
    '/products',
    '/products/:id',
    '/inspections/:id',
    '/reports',
  ],
  REVIEWER: [
    '/dashboard',
    '/products',
    '/products/:id',
    '/inspections/:id',
    '/reports',
  ],
};
