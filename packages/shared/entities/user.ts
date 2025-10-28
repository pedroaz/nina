import mongoose from 'mongoose';

export interface User extends mongoose.Document {
    name: string;
    email: string;
}

export const userSchema = new mongoose.Schema({
    name: String,
    email: String
});

export const UserModel =
    (mongoose.models.users as mongoose.Model<User> | undefined) ??
    mongoose.model<User>('users', userSchema);
