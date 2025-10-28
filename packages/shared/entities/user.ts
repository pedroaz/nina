import mongoose from 'mongoose';

export interface User extends mongoose.Document {
    name: string;
    email: string;
}

export const userSchema = new mongoose.Schema({
    name: String,
    email: String
});

export const UserModel = mongoose.model<User>('users', userSchema);
