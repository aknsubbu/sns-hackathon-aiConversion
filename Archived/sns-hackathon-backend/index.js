const express = require("express");
const morgan = require("morgan");
const jsonwebtoken = require("jsonwebtoken");
const bodyParser = require("body-parser");
require("dotenv").config();
const cors = require("cors");
const mongoose = require("mongoose");
const app = express();
app.use(cors());
app.use(bodyParser.json());
app.use(morgan("dev"));

const port = process.env.PORT || 3000;

const databaseurl =
  process.env.DATABASE_URL ||
  "mongodb+srv://abinav:7RK22ZlEesfW8lyL@cluster0.7r4wtvv.mongodb.net/";

const UserSchema = require("./models/UserModel");
const VideoSchema = require("./models/VideoSchema");

mongoose.connect(databaseurl, {
  useNewUrlParser: true,
  useUnifiedTopology: true,
});
mongoose.connection.on("connected", () => {
  console.log("Mongoose is connected!!!!");
});

app.get("/", (req, res) => {
  res.json({
    message: "Welcome to the API",
  });
});

const authentication = (req, res, next) => {
  if (req.headers.authentication_type === "User") {
    const token = req.headers.authentication_credentials;
    const decoded = jsonwebtoken.verify(token, "SECRET_KEY");
    console.log(decoded);
    if (decoded.role === "User") {
      next();
    } else {
      res.status(401).json({ message: "Invalid credentials" });
    }
  } else {
    console.log(req.headers);
    console.log(req.headers.authentication_type);
    res.status(401).json({ message: "Invalid credentials" });
  }
};

app.post("/login", (req, res) => {
  try {
    const { username, password } = req.body;
    UserSchema.find({ username: username }).then((data) => {
      if (data.length == 0) {
        res.status(401).json({ message: "Invalid credentials" });
      } else {
        if (data[0].password == password) {
          const token = jsonwebtoken.sign(
            {
              userID: data[0]._id,
              role: "user",
            },
            "SECRET_KEY"
          );
          console.log(data[0].username, data[0].email, data[0]._id);
          res.status(200).json({
            token: token,
            authentication: { type: "user", credentials: token },
          });
        } else {
          res.status(401).json({ message: "Invalid credentials" });
        }
      }
    });
  } catch (error) {
    res.status(500).json({ message: error.message });
  }
});

app.post("/register", (req, res) => {
  try {
    const { username, email, password } = req.body;
    UserSchema.find({ username: username }).then((data) => {
      if (data.length == 0) {
        const user = new UserSchema({
          username: username,
          email: email,
          password: password,
        });
        user.save().then((data) => {
          res.status(200).json({ message: "User created successfully" });
        });
      } else {
        res.status(401).json({ message: "User already exists" });
      }
    });
  } catch (error) {
    res.status(500).json({ message: error.message });
  }
});

app.post("/api/getvideos", authentication, async (req, res) => {
  try {
    const { userId } = req.body;
    const videos = await VideoSchema.find({ userId: userId });
    res.status(200).json({ videos: videos });
  } catch (error) {
    res.status(500).json({ message: error.message });
  }
});

app.listen(port, () => {
  console.log(`listening on port ${port}`);
});
