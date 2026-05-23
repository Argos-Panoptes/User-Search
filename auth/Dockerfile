FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN apk add --no-cache curl && npm install

COPY . .

EXPOSE 9000

CMD ["npm", "start"]
