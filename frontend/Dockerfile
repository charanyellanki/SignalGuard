FROM node:20-alpine

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 5173

# Dev server — hot reload while iterating on the dashboard.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
